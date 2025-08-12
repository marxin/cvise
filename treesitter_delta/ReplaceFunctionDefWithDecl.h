#ifndef REPLACE_FUNCTION_FUNC_DEF_WITH_DECL_H
#define REPLACE_FUNCTION_FUNC_DEF_WITH_DECL_H

#include <memory>
#include <string>

#include <tree_sitter/api.h>

// Emits hints that deletes function bodies (either replacing them with
// semicolons or deleting the whole definition altogether).
class FuncDefWithDeclReplacer {
public:
  FuncDefWithDeclReplacer();
  ~FuncDefWithDeclReplacer();
  void processFile(const std::string &FileContents, TSTree &Tree);

private:
  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
};

#endif
