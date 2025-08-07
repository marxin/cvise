#ifndef REPLACE_FUNCTION_FUNC_DEF_WITH_DECL_H
#define REPLACE_FUNCTION_FUNC_DEF_WITH_DECL_H

#include <cstdint>
#include <memory>

#include <tree_sitter/api.h>

// Emits hints that deletes function bodies (either replacing them with
// semicolons or deleting the whole definition altogether).
class FuncDefWithDeclReplacer {
public:
  FuncDefWithDeclReplacer();
  ~FuncDefWithDeclReplacer();
  void processParsedFile(TSTree &Tree);

private:
  struct Instance {
    uint32_t StartByte = 0;
    uint32_t EndByte = 0;
    bool WriteSemicolon = false;
  };

  static bool overlaps(const Instance &A, const Instance &B);
  static void printAsHint(const Instance &Inst);

  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
};

#endif
