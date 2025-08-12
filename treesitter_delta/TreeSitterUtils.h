#ifndef TREE_SITTER_UTILS_H
#define TREE_SITTER_UTILS_H

#include <string>

#include <tree_sitter/api.h>

std::string getNodeText(const TSNode &Node, const std::string &FileContents);
TSNode walkUpNodeWithType(const TSNode &FuncDef, const std::string &NeededType);

#endif
