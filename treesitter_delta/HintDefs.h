#ifndef HINT_DEFS_H
#define HINT_DEFS_H

// The hints vocabulary.
inline constexpr const char *HintsVocabulary[] = {
    "replace-function-def-with-decl",
    ";",
};
// The indices must match the order in HintsVocabulary.
constexpr int ReplaceFuncDefWithDeclVocabIdx = 0;
constexpr int SemicolonVocabIdx = 1;

#endif
