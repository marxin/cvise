#include "EraseNamespace.h"

#include "Parsers.h"
#include "TreeSitterUtils.h"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <utility>

#include <tree_sitter/api.h>

// Searches namespace definitions with nonempty bodies (at least one child in
// the curly-surrounded block). Captures the body.
constexpr char QueryStr[] = R"(
  (
    namespace_definition
    body: (
      _ (_)
    ) @capture0
  )
)";

NamespaceEraser::NamespaceEraser() : Query(nullptr, ts_query_delete) {
  uint32_t ErrorOffset = 0;
  TSQueryError ErrorType = TSQueryErrorNone;
  Query.reset(ts_query_new(tree_sitter_cpp(), QueryStr, std::size(QueryStr) - 1,
                           &ErrorOffset, &ErrorType));
  if (!Query) {
    std::cerr << "Failed to init Tree-sitter query: error " << ErrorType
              << " offset " << ErrorOffset << "\n";
    std::exit(-1);
  }
}

NamespaceEraser::~NamespaceEraser() = default;

std::vector<std::string> NamespaceEraser::getVocabulary() const {
  // The string that's used by the hints emitted below.
  return {"{}"};
}

void NamespaceEraser::processFile(const std::string &FileContents, TSTree &Tree,
                                  std::optional<int> PathId) {
  std::unique_ptr<TSQueryCursor, decltype(&ts_query_cursor_delete)> Cursor(
      ts_query_cursor_new(), ts_query_cursor_delete);
  ts_query_cursor_exec(Cursor.get(), Query.get(), ts_tree_root_node(&Tree));

  TSQueryMatch Match;
  while (ts_query_cursor_next_match(Cursor.get(), &Match)) {
    assert(Match.capture_count == 1);
    const TSNode &Body = Match.captures[0].node;
    uint32_t StartByte = ts_node_start_byte(Body);
    uint32_t EndByte = ts_node_end_byte(Body);
    // The number "0" refers to the string returned from getVocabulary().
    std::cout << "{\"p\":[{\"l\":" << StartByte << ",\"r\":" << EndByte
              << ",\"v\":0";
    if (PathId.has_value())
      std::cout << ",\"p\":" << *PathId;
    std::cout << "}]}\n";
  }
}
