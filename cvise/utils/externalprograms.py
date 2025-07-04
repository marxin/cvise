import os
import platform
import shutil

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
DESTDIR = os.getenv('DESTDIR', '')


def find_external_programs():
    programs = {
        'clang_delta': 'clang_delta',
        'clex': 'clex',
        'topformflat_hints': 'delta',
        'unifdef': None,
        'gcov-dump': None,
    }

    for prog, local_folder in programs.items():
        path = None
        if local_folder:
            local_folder = os.path.join(SCRIPT_PATH, '..', '..', local_folder)
            if platform.system() == 'Windows':
                for configuration in ['Debug', 'Release']:
                    new_local_folder = os.path.join(local_folder, configuration)
                    if os.path.exists(new_local_folder):
                        local_folder = new_local_folder
                        break

            path = shutil.which(prog, path=local_folder)

            if not path:
                search = os.path.join('@CMAKE_INSTALL_FULL_LIBEXECDIR@', '@cvise_PACKAGE@')
                path = shutil.which(prog, path=search)
            if not path:
                search = DESTDIR + os.path.join('@CMAKE_INSTALL_FULL_LIBEXECDIR@', '@cvise_PACKAGE@')
                path = shutil.which(prog, path=search)

        if not path:
            path = shutil.which(prog)

        if path is not None:
            programs[prog] = path

    # Special case for clang-format
    programs['clang-format'] = '@CLANG_FORMAT_PATH@'

    return programs
