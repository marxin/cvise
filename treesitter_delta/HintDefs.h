#ifndef HINT_DEFS_H
#define HINT_DEFS_H

// The hints vocabulary - the list of strings that hints can refer to.
inline constexpr const char *HintsVocab[] = {
    "replace-function-def-with-decl",
    ";",
};
// The order must match the order in HintsVocabulary.
enum class HintsVocabId {
  ReplaceFuncDefWithDecl,
  Semicolon,
};

#endif
