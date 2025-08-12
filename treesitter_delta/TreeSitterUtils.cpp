#include "TreeSitterUtils.h"

#include <cassert>
#include <cstdint>
#include <string>

#include <tree_sitter/api.h>

std::string getNodeText(const TSNode &Node, const std::string &FileContents) {
  uint32_t Start = ts_node_start_byte(Node);
  uint32_t End = ts_node_end_byte(Node);
  assert(Start <= End);
  return FileContents.substr(Start, End - Start);
}

TSNode walkUpNodeWithType(const TSNode &FuncDef,
                          const std::string &NeededType) {
  TSNode Current = FuncDef;
  TSNode
      Template{}; // zero-initialize to return null if the parent doesn't match
  for (;;) {
    TSNode Parent = ts_node_parent(Current);
    if (ts_node_is_null(Parent) || ts_node_type(Parent) != NeededType)
      break;
    Current = Parent;
    Template = Parent;
  }
  return Template;
}
