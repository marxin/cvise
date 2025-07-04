from dataclasses import dataclass
import json
import logging
import os
from typing import List

from cvise.passes.abstract import AbstractPass
from cvise.passes.balanced import BalancedPass
from cvise.passes.blank import BlankPass
from cvise.passes.clang import ClangPass
from cvise.passes.clangbinarysearch import ClangBinarySearchPass
from cvise.passes.clex import ClexPass
from cvise.passes.comments import CommentsPass
from cvise.passes.gcdabinary import GCDABinaryPass
from cvise.passes.ifs import IfPass
from cvise.passes.includeincludes import IncludeIncludesPass
from cvise.passes.includes import IncludesPass
from cvise.passes.indent import IndentPass
from cvise.passes.ints import IntsPass
from cvise.passes.line_markers import LineMarkersPass
from cvise.passes.lines import LinesPass
from cvise.passes.peep import PeepPass
from cvise.passes.special import SpecialPass
from cvise.passes.ternary import TernaryPass
from cvise.passes.unifdef import UnIfDefPass
from cvise.utils import keyboard_interrupt_monitor
from cvise.utils.error import CViseError, PassOptionError


class CVise:
    class Info:
        PACKAGE_BUGREPORT = '@cvise_PACKAGE_BUGREPORT@'
        PACKAGE_NAME = '@cvise_PACKAGE_NAME@'
        PACKAGE_STRING = '@cvise_PACKAGE_STRING@'
        PACKAGE_URL = '@cvise_PACKAGE_URL@'
        PACKAGE_VERSION = '@cvise_PACKAGE_VERSION@'

        VERSION = '@cvise_VERSION@'
        GIT_VERSION = '@GIT_HASH@'
        LLVM_VERSION = '@LLVM_VERSION@'

    @dataclass
    class PassCategory:
        name: str
        log_title: str
        initial: bool
        once: bool

    PASS_CATEGORIES = [
        # "first" categories (executed once)
        PassCategory(name='first', log_title='INITIAL PASSES', initial=True, once=True),
        # "main" categories (looped)
        PassCategory(name='main', log_title='MAIN PASSES', initial=False, once=False),
        # "last" category (executed once)
        PassCategory(name='last', log_title='CLEANUP PASSES', initial=False, once=True),
    ]

    pass_name_mapping = {
        'balanced': BalancedPass,
        'blank': BlankPass,
        'clang': ClangPass,
        'clangbinarysearch': ClangBinarySearchPass,
        'clex': ClexPass,
        'comments': CommentsPass,
        'gcda-binary': GCDABinaryPass,
        'ifs': IfPass,
        'includeincludes': IncludeIncludesPass,
        'includes': IncludesPass,
        'indent': IndentPass,
        'ints': IntsPass,
        'line_markers': LineMarkersPass,
        'lines': LinesPass,
        'peep': PeepPass,
        'special': SpecialPass,
        'ternary': TernaryPass,
        'unifdef': UnIfDefPass,
    }

    def __init__(self, test_manager, skip_interestingness_test_check):
        keyboard_interrupt_monitor.init()
        self.test_manager = test_manager
        self.skip_interestingness_test_check = skip_interestingness_test_check
        self.tidy = False

    @classmethod
    def load_pass_group_file(cls, path):
        with open(path) as pass_group_file:
            try:
                pass_group_dict = json.load(pass_group_file)
            except json.JSONDecodeError:
                raise CViseError('Not valid JSON.') from None

        return pass_group_dict

    @classmethod
    def parse_pass_group_dict(
        cls,
        pass_group_dict,
        pass_options,
        external_programs,
        remove_pass,
        clang_delta_std,
        clang_delta_preserve_routine,
        not_c,
        renaming,
    ):
        pass_group = {}
        removed_passes = set(remove_pass.split(',')) if remove_pass else set()

        def parse_options(options):
            valid_options = set()

            for opt in options:
                try:
                    valid_options.add(AbstractPass.Option(opt))
                except ValueError:
                    raise PassOptionError(opt) from None

            return valid_options

        def include_pass(pass_dict, options):
            return (('include' not in pass_dict) or bool(parse_options(pass_dict['include']) & options)) and (
                ('exclude' not in pass_dict) or not bool(parse_options(pass_dict['exclude']) & options)
            )

        for category in cls.PASS_CATEGORIES:
            if category.name not in pass_group_dict:
                raise CViseError(f'Missing category {category}')

            pass_group[category.name] = []

            for pass_dict in pass_group_dict[category.name]:
                if not include_pass(pass_dict, pass_options):
                    continue

                if 'pass' not in pass_dict:
                    raise CViseError(f'Invalid pass in category {category.name}')

                try:
                    pass_class = cls.pass_name_mapping[pass_dict['pass']]
                except KeyError:
                    raise CViseError('Unknown pass {}'.format(pass_dict['pass'])) from None

                pass_instance = pass_class(pass_dict.get('arg'), external_programs)
                pass_instance.max_transforms = None
                if str(pass_instance) in removed_passes:
                    continue

                if not_c and 'c' in pass_dict and pass_dict['c']:
                    continue
                elif not renaming and 'renaming' in pass_dict and pass_dict['renaming']:
                    continue

                try:
                    pass_instance.max_transforms = int(pass_dict['max-transforms'])
                except KeyError:
                    pass

                pass_instance.user_clang_delta_std = clang_delta_std
                pass_instance.clang_delta_preserve_routine = clang_delta_preserve_routine
                pass_group[category.name].append(pass_instance)

        return pass_group

    def reduce(self, pass_group, skip_initial):
        self._check_prerequisites(pass_group)
        if not self.skip_interestingness_test_check:
            self.test_manager.check_sanity(True)

        logging.info(f'===< {os.getpid()} >===')
        logging.info(
            'running {} interestingness test{} in parallel'.format(
                self.test_manager.parallel_tests,
                '' if self.test_manager.parallel_tests == 1 else 's',
            )
        )

        if not self.tidy:
            self.test_manager.backup_test_cases()

        for category_name, passes in pass_group.items():
            category = next(c for c in self.PASS_CATEGORIES if c.name == category_name)
            if skip_initial and category.initial:
                continue
            logging.info('%s', category.log_title)
            self._run_pass_category(passes, category)

        logging.info('===================== done ====================')
        return True

    @staticmethod
    def _check_prerequisites(pass_group):
        for category in pass_group:
            for p in pass_group[category]:
                if not p.check_prerequisites():
                    logging.error(f'Prereqs not found for pass {p}')

    def _run_pass_category(self, passes: List[AbstractPass], category: PassCategory) -> None:
        if category.once:
            self._run_passes(passes, check_threshold=False)
        else:
            while True:
                total_file_size = self.test_manager.total_file_size
                met_stopping_threshold = self._run_passes(passes, check_threshold=True)
                logging.info(f'Termination check: size was {total_file_size}; now {self.test_manager.total_file_size}')
                if (self.test_manager.total_file_size >= total_file_size) or met_stopping_threshold:
                    break

    def _run_passes(self, passes: List[AbstractPass], check_threshold: bool) -> None:
        """Runs the given passes once; returns whether the stopping threshold was met."""
        available_passes = []
        for p in passes:
            if not p.check_prerequisites():
                logging.error(f'Skipping pass {p}')
            else:
                available_passes.append(p)
        if not available_passes:
            return False

        for p in available_passes:
            # Exit early if we're already reduced enough
            if check_threshold and self._met_stopping_threshold():
                return True
            self.test_manager.run_passes([p])
        return check_threshold and self._met_stopping_threshold()

    def _met_stopping_threshold(self) -> bool:
        improvement = (
            self.test_manager.orig_total_file_size - self.test_manager.total_file_size
        ) / self.test_manager.orig_total_file_size
        logging.debug(
            f'Termination check: stopping threshold is {self.test_manager.stopping_threshold}; current improvement is {improvement:.1f}'
        )
        return improvement >= self.test_manager.stopping_threshold
