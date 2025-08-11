#ifndef REMOVE_FUNCTION_H
#define REMOVE_FUNCTION_H

#include <memory>
#include <string>

#include <tree_sitter/api.h>

class FunctionRemover {
public:
  FunctionRemover();
  ~FunctionRemover();
  void processFile(const std::string &FileContents, TSTree &Tree);

private:
  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
};

#endif
