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
