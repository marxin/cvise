#include "EraseNamespace.h"

#include "Parsers.h"
#include "TreeSitterUtils.h"

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <map>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <tree_sitter/api.h>

static void
printRanges(const std::vector<std::pair<uint32_t, uint32_t>> &Ranges) {
  std::cout << "{\"p\":[";
  for (size_t I = 0; I < Ranges.size(); ++I) {
    if (I > 0)
      std::cout << ",";
    // The "v" number must match the order in the printed hint vocabulary.
    std::cout << "{\"l\":" << Ranges[I].first << ",\"r\":" << Ranges[I].second
              << ",\"v\":0}";
  }
  std::cout << "]}\n";
}

NamespaceEraser::NamespaceEraser() : Query(nullptr, ts_query_delete) {
  constexpr char QueryStr[] = R"(
    (
      namespace_definition
      name: (namespace_identifier)? @capture0
      body: (
        _ (_)
      ) @capture1
    )
  )";
  uint32_t ErrorOffset = 0;
  TSQueryError ErrorType = TSQueryErrorNone;
  Query.reset(ts_query_new(tree_sitter_cpp(), QueryStr, std::size(QueryStr) - 1,
                           &ErrorOffset, &ErrorType));
  if (!Query) {
    std::cerr << "Failed to init Tree-sitter query: error " << ErrorType
              << " offset " << ErrorOffset << "\n";
    std::exit(-1);
  }
  // Print the hint vocabulary - in our case it's only the empty pair of curly
  // braces that the hints can refer to.
  std::cout << "[\"{}\"]\n";
}

NamespaceEraser::~NamespaceEraser() = default;

void NamespaceEraser::processFile(const std::string &FileContents,
                                  TSTree &Tree) {
  std::unique_ptr<TSQueryCursor, decltype(&ts_query_cursor_delete)> Cursor(
      ts_query_cursor_new(), ts_query_cursor_delete);
  ts_query_cursor_exec(Cursor.get(), Query.get(), ts_tree_root_node(&Tree));

  std::map<std::string, std::vector<std::pair<uint32_t, uint32_t>>>
      NameToRanges;
  TSQueryMatch Match;
  while (ts_query_cursor_next_match(Cursor.get(), &Match)) {
    TSNode Body;
    std::string Name;
    if (Match.capture_count == 1) {
      Body = Match.captures[0].node;
    } else {
      if (Match.captures[1].index != 1)
        std::abort();
      Name = getNodeText(Match.captures[0].node, FileContents);
      Body = Match.captures[1].node;
    }
    uint32_t StartByte = ts_node_start_byte(Body);
    uint32_t EndByte = ts_node_end_byte(Body);
    NameToRanges[Name].emplace_back(StartByte, EndByte);
  }

  for (const auto &[Name, Ranges] : NameToRanges) {
    if (Name.empty()) {
      // Each unnamed namespace is attempted to be erased independently.
      for (const auto &Range : Ranges)
        printRanges({Range});
    } else {
      // Attempt erasing all occurrences of the namespace with the given name.
      printRanges(Ranges);
    }
  }
}
