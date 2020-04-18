import re

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils.error import UnknownArgumentError

class IntsPass(AbstractPass):
    border_or_space = r"(?:(?:[*,:;{}[\]()])|\s)"

    def check_prerequisites(self):
        return True

    def __get_config(self):
        config = {"search": None,
                  "replace_fn": None,
                 }

        if self.arg == "a":
            # Delete first digit
            def replace_fn(m):
                return m.group("pref") + m.group("numpart") + m.group("suf")

            config["search"] = r"(?P<pref>" + self.border_or_space + r"[+-]?(?:0|(?:0[xX]))?)[0-9a-fA-F](?P<numpart>[0-9a-fA-F]+)(?P<suf>[ULul]*" + self.border_or_space + r")"
        elif self.arg == "b":
            # Delete prefix
            def replace_fn(m):
                return m.group("del") + m.group("numpart") + m.group("suf")

            config["search"] = r"(?P<del>" + self.border_or_space + r")(?P<pref>[+-]?(?:0|(?:0[xX])))(?P<numpart>[0-9a-fA-F]+)(?P<suf>[ULul]*" + self.border_or_space + r")"
        elif self.arg == "c":
            # Delete suffix
            def replace_fn(m):
                return m.group("pref") + m.group("numpart") + m.group("del")

            config["search"] = r"(?P<pref>" + self.border_or_space + r"[+-]?(?:0|(?:0[xX]))?)(?P<numpart>[0-9a-fA-F]+)[ULul]+(?P<del>" + self.border_or_space + r")"
        elif self.arg == "d":
            # Hex to dec
            def replace_fn(m):
                return m.group("pref") + str(int(m.group("numpart"), 16)) + m.group("suf")

            config["search"] = r"(?P<pref>" + self.border_or_space + r")(?P<numpart>0[Xx][0-9a-fA-F]+)(?P<suf>[ULul]*" + self.border_or_space + r")"
        else:
            raise UnknownArgumentError()

        config["replace_fn"] = replace_fn
        return config

    def new(self, test_case):
        config = self.__get_config()
        with open(test_case, "r") as in_file:
            prog = in_file.read()
            regex = re.compile(config["search"], flags=re.DOTALL)
            modifications = list(reversed([(m.span(), config["replace_fn"](m)) for m in regex.finditer(prog)]))
            if not modifications:
                return None
            return {"modifications": modifications, "index": 0}

    def advance(self, test_case, state):
        state = state.copy()
        state["index"] += 1
        if state["index"] >= len(state["modifications"]):
            return None
        return state

    def advance_on_success(self, test_case, state):
        return self.new(test_case)

    def transform(self, test_case, state):
        with open(test_case, "r") as in_file:
            data = in_file.read()
            index = state["index"]
            ((start, end), replacement) = state["modifications"][index]
            new_data = data[:start] + replacement + data[end:]
            with open(test_case, "w") as out_file:
                out_file.write(new_data)
                return (PassResult.OK, state)
