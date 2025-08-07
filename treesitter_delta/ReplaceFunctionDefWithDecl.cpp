#include "ReplaceFunctionDefWithDecl.h"

#include "HintDefs.h"
#include "Parsers.h"

#include <algorithm>
#include <array>
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
    declarator: (
      function_declarator
      declarator: (
        qualified_identifier
      )? @capture0
    )
    (field_initializer_list)? @capture1
    body: (_) @capture2
  ) @capture3
)";

static void getMatchCaptures(const TSQueryMatch &Match, TSNode &QualId,
                             TSNode &InitList, TSNode &Body, TSNode &FuncDef) {
  // The capture count and indices must match those specified in QueryStr.
  std::array<TSNode, 4> Captures{}; // zero-initialize to recognize null nodes
  for (int I = 0; I < Match.capture_count; ++I)
    Captures.at(Match.captures[I].index) = Match.captures[I].node;
  QualId = Captures[0];
  InitList = Captures[1];
  Body = Captures[2];
  FuncDef = Captures[3];
}

static TSNode walkUpTemplateDecls(const TSNode &FuncDef) {
  TSNode Ancestor = FuncDef;
  for (;;) {
    TSNode Parent = ts_node_parent(Ancestor);
    if (ts_node_is_null(Parent) ||
        ts_node_type(Parent) != std::string("template_declaration")) {
      break;
    }
    Ancestor = Parent;
  }
  return Ancestor;
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
}

FuncDefWithDeclReplacer::~FuncDefWithDeclReplacer() = default;

void FuncDefWithDeclReplacer::processParsedFile(TSTree &Tree) {
  std::unique_ptr<TSQueryCursor, decltype(&ts_query_cursor_delete)> Cursor(
      ts_query_cursor_new(), ts_query_cursor_delete);
  ts_query_cursor_exec(Cursor.get(), Query.get(), ts_tree_root_node(&Tree));

  std::vector<Instance> AllInst;
  TSQueryMatch Match;
  while (ts_query_cursor_next_match(Cursor.get(), &Match)) {
    TSNode QualId, InitList, Body, FuncDef;
    getMatchCaptures(Match, QualId, InitList, Body, FuncDef);

    // In the basic case, we replace the function body with a semicolon.
    Instance Inst{
        .StartByte = ts_node_start_byte(Body),
        .EndByte = ts_node_end_byte(Body),
        .WriteSemicolon = true,
    };
    if (!ts_node_is_null(QualId)) {
      // An out-of-line declaration of a member has to be deleted completely.
      Inst.StartByte = ts_node_start_byte(walkUpTemplateDecls(FuncDef));
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

bool FuncDefWithDeclReplacer::overlaps(const Instance &A, const Instance &B) {
  return std::max(A.StartByte, B.StartByte) < std::min(A.EndByte, B.EndByte);
}

void FuncDefWithDeclReplacer::printAsHint(const Instance &Inst) {
  std::cout << "{\"t\":"
            << static_cast<int>(HintsVocabId::ReplaceFuncDefWithDecl)
            << ",\"p\":[{\"l\":" << Inst.StartByte << ",\"r\":" << Inst.EndByte;
  if (Inst.WriteSemicolon)
    std::cout << ",\"v\":" << static_cast<int>(HintsVocabId::Semicolon);
  std::cout << "}]}\n";
}
