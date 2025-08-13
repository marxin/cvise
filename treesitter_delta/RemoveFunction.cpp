#include "RemoveFunction.h"

#include "Parsers.h"
#include "TreeSitterUtils.h"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <memory>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include <sys/types.h>
#include <tree_sitter/api.h>

// Searches for function declarations and definitions. Captures the function
// name, ignoring the qualified identifier namespaces.
//
// Note: The captures here must match constants in getMatchCaptures().
constexpr char QueryStr[] = R"(
  (
    [
      (
        function_definition
        declarator: (
          function_declarator
          declarator: [
            (identifier) @capture0
            (field_identifier) @capture1
            (destructor_name (identifier) @capture2)
            (qualified_identifier name: (identifier) @capture3)
            (qualified_identifier name: (
              qualified_identifier name: (identifier) @capture4))
          ]
        )
      )
      (
        declaration
        declarator: (
          function_declarator
          declarator: (identifier) @capture5
        )
      )
      (
        field_declaration
        declarator: (
          function_declarator
          declarator: (field_identifier) @capture6
        )
      )
    ]
  ) @capture7
)";

namespace {

struct Instance {
  uint32_t StartByte = 0;
  uint32_t EndByte = 0;

  bool operator<(const Instance &Other) const {
    return std::tie(StartByte, EndByte) <
           std::tie(Other.StartByte, Other.EndByte);
  }
};

using NameToInstanceVec = std::map<std::string, std::vector<Instance>>;

// Compares two names by their instance vectors, lexicographically.
struct InstancesComparator {
  explicit InstancesComparator(const NameToInstanceVec &InstancesByName)
      : InstancesByName(InstancesByName) {}

  bool operator()(const std::string &A, const std::string &B) const {
    return InstancesByName.at(A) < InstancesByName.at(B);
  }

  const NameToInstanceVec &InstancesByName;
};

} // namespace

static void getMatchCaptures(const TSQueryMatch &Match,
                             const std::string &FileContents, std::string &Name,
                             TSNode &Func) {
  // The indices must match those specified in QueryStr.
  assert(Match.capture_count == 2);
  for (int I = 0; I < Match.capture_count; ++I) {
    const TSNode &N = Match.captures[I].node;
    uint32_t Capture = Match.captures[I].index;
    if (Capture == 7) { // the whole match
      Func = N;
      continue;
    }
    Name = getNodeText(N, FileContents);
    if (Capture == 2)
      Name = "~" + Name; // destructor;
  }
}

FunctionRemover::FunctionRemover() : Query(nullptr, ts_query_delete) {
  uint32_t ErrorOffset = 0;
  TSQueryError ErrorType = TSQueryErrorNone;
  Query.reset(ts_query_new(tree_sitter_cpp(), QueryStr, std::size(QueryStr) - 1,
                           &ErrorOffset, &ErrorType));
  if (!Query) {
    std::cerr << "Failed to init Tree-sitter query: error " << ErrorType
              << " offset " << ErrorOffset << "\n";
    std::exit(-1);
  }
  // The (empty) hint vocabulary.
  std::cout << "[]\n";
}

FunctionRemover::~FunctionRemover() = default;

void FunctionRemover::processFile(const std::string &FileContents,
                                  TSTree &Tree) {
  std::unique_ptr<TSQueryCursor, decltype(&ts_query_cursor_delete)> Cursor(
      ts_query_cursor_new(), ts_query_cursor_delete);
  ts_query_cursor_exec(Cursor.get(), Query.get(), ts_tree_root_node(&Tree));

  TSQueryMatch Match;
  NameToInstanceVec InstancesByName;
  while (ts_query_cursor_next_match(Cursor.get(), &Match)) {
    std::string Name;
    TSNode Func;
    getMatchCaptures(Match, FileContents, Name, Func);
    // When removing, start from the "template <" node if present.
    TSNode Template = walkUpNodeWithType(Func, "template_declaration");
    TSNode ToRemove = ts_node_is_null(Template) ? Func : Template;
    InstancesByName[Name].push_back({.StartByte = ts_node_start_byte(ToRemove),
                                     .EndByte = ts_node_end_byte(ToRemove)});
  }

  // We want to emit hints in a monotonic order, so that functions located close
  // to each other in the input test are also attempted to be deleted together
  // as part of the binary search logic. For this, sort names by their instance
  // byte indices.
  std::vector<std::string> Names;
  Names.reserve(InstancesByName.size());
  for (const auto &[Name, Instances] : InstancesByName)
    Names.push_back(Name);
  std::sort(Names.begin(), Names.end(), InstancesComparator(InstancesByName));

  for (const auto &Name : Names) {
    const auto &Instances = InstancesByName.at(Name);
    std::cout << "{\"p\":[";
    for (size_t I = 0; I < Instances.size(); ++I) {
      if (I > 0)
        std::cout << ",";
      std::cout << "{\"l\":" << Instances[I].StartByte
                << ",\"r\":" << Instances[I].EndByte << "}";
    }
    std::cout << "]}\n";
  }
}
