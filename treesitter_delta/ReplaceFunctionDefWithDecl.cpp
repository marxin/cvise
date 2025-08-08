#include "ReplaceFunctionDefWithDecl.h"

#include "Parsers.h"

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <tree_sitter/api.h>

// The captures here must match constants in getMatchCaptures().
constexpr char QueryStr[] = R"(
  (
    function_definition
    (type_qualifier)* @capture0
    declarator: (
      function_declarator
      declarator: (
        qualified_identifier
      )? @capture1
    )
    (field_initializer_list)? @capture2
    body: (_) @capture3
  ) @capture4
)";

namespace {

struct Instance {
  uint32_t StartByte = 0;
  uint32_t EndByte = 0;
  bool IsTemplate = false;
  bool WriteSemicolon = false;
};

} // namespace

static bool overlaps(const Instance &A, const Instance &B) {
  return std::max(A.StartByte, B.StartByte) < std::min(A.EndByte, B.EndByte);
}

static void printAsHint(const Instance &Inst) {
  // The numbers here must match the order in the vocabulary printed below.
  std::cout << "{\"t\":" << (Inst.IsTemplate ? 2 : 1)
            << ",\"p\":[{\"l\":" << Inst.StartByte << ",\"r\":" << Inst.EndByte;
  if (Inst.WriteSemicolon)
    std::cout << ",\"v\":0";
  std::cout << "}]}\n";
}

static std::string getNodeText(const TSNode &Node,
                               const std::string &FileContents) {
  uint32_t Start = ts_node_start_byte(Node);
  uint32_t End = ts_node_end_byte(Node);
  assert(Start <= End);
  return FileContents.substr(Start, End - Start);
}

static void getMatchCaptures(const TSQueryMatch &Match,
                             const std::string &FileContents,
                             TSNode &ConstexprQual, TSNode &QualId,
                             TSNode &InitList, TSNode &Body, TSNode &FuncDef) {
  for (int I = 0; I < Match.capture_count; ++I) {
    const TSNode &N = Match.captures[I].node;
    // The indices must match those specified in QueryStr.
    switch (Match.captures[I].index) {
    case 0:
      if (getNodeText(N, FileContents) == "constexpr")
        ConstexprQual = N;
      break;
    case 1:
      QualId = N;
      break;
    case 2:
      InitList = N;
      break;
    case 3:
      Body = N;
      break;
    case 4:
      FuncDef = N;
      break;
    default:
      assert(false);
    }
  }
}

static TSNode walkUpTemplateDecls(const TSNode &FuncDef) {
  TSNode Current = FuncDef;
  TSNode Template{}; // zero-initialize to return null for non-template cases
  for (;;) {
    TSNode Parent = ts_node_parent(Current);
    if (ts_node_is_null(Parent) ||
        ts_node_type(Parent) != std::string("template_declaration")) {
      break;
    }
    Current = Parent;
    Template = Parent;
  }
  return Template;
}

FuncDefWithDeclReplacer::FuncDefWithDeclReplacer()
    : Query(nullptr, ts_query_delete) {
  uint32_t ErrorOffset = 0;
  TSQueryError ErrorType = TSQueryErrorNone;
  Query.reset(ts_query_new(tree_sitter_cpp(), QueryStr, std::size(QueryStr) - 1,
                           &ErrorOffset, &ErrorType));
  if (!Query) {
    std::cerr << "Failed to init Tree-sitter query: error " << ErrorType
              << " offset " << ErrorOffset << "\n";
    std::exit(-1);
  }

  // Print the hint vocabulary - the strings that hints can refer to.
  std::cout << "[\";\",\"regular\",\"template-function\"]\n";
}

FuncDefWithDeclReplacer::~FuncDefWithDeclReplacer() = default;

void FuncDefWithDeclReplacer::processFile(const std::string &FileContents,
                                          TSTree &Tree) {
  std::unique_ptr<TSQueryCursor, decltype(&ts_query_cursor_delete)> Cursor(
      ts_query_cursor_new(), ts_query_cursor_delete);
  ts_query_cursor_exec(Cursor.get(), Query.get(), ts_tree_root_node(&Tree));

  std::vector<Instance> AllInst;
  TSQueryMatch Match;
  while (ts_query_cursor_next_match(Cursor.get(), &Match)) {
    TSNode ConstexprQual{}, QualId{}, InitList{}, Body{},
        FuncDef{}; // zero-initialize to recognize null nodes
    getMatchCaptures(Match, FileContents, ConstexprQual, QualId, InitList, Body,
                     FuncDef);

    if (!ts_node_is_null(ConstexprQual)) {
      // The heuristic isn't applicable to constexpr functions.
      continue;
    }

    TSNode Template = walkUpTemplateDecls(FuncDef);

    // In the basic case, we replace the function body with a semicolon.
    Instance Inst{
        .StartByte = ts_node_start_byte(Body),
        .EndByte = ts_node_end_byte(Body),
        .IsTemplate = !ts_node_is_null(Template),
        .WriteSemicolon = true,
    };
    if (!ts_node_is_null(QualId)) {
      // An out-of-line member has to be deleted completely. Start from the
      // "template <" token if it's a function template or a template class'
      // method or both.
      Inst.StartByte = ts_node_start_byte(Inst.IsTemplate ? Template : FuncDef);
      Inst.WriteSemicolon = false;
    } else if (!ts_node_is_null(InitList)) {
      // In case of a constructor, initializer lists have to be deleted as well.
      Inst.StartByte = ts_node_start_byte(InitList);
    }
    assert(Inst.StartByte < Inst.EndByte);

    // Delete overlapping segments: leave only the most detailed matches. This
    // is to combat the cases when Tree-sitter mistakenly perceives a
    // class/namespace as a function (usually caused by macros).
    while (!AllInst.empty() && overlaps(AllInst.back(), Inst))
      AllInst.pop_back();
    AllInst.push_back(Inst);
  }

  for (const auto &Inst : AllInst)
    printAsHint(Inst);
}
