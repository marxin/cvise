#ifndef REPLACE_FUNCTION_FUNC_DEF_WITH_DECL_H
#define REPLACE_FUNCTION_FUNC_DEF_WITH_DECL_H

#include <memory>
#include <optional>
#include <string>

#include <tree_sitter/api.h>

#include "Transformation.h"

// Emits hints that deletes function bodies (either replacing them with
// semicolons or deleting the whole definition altogether).
class FuncDefWithDeclReplacer : public Transformation {
public:
  FuncDefWithDeclReplacer();
  ~FuncDefWithDeclReplacer() override;
  std::vector<std::string> getVocabulary() const override;
  void processFile(const std::string &FileContents, TSTree &Tree,
                   std::optional<int> PathId) override;

private:
  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
};

#endif
