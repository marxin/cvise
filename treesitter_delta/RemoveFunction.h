#ifndef REMOVE_FUNCTION_H
#define REMOVE_FUNCTION_H

#include <memory>
#include <string>

#include <tree_sitter/api.h>

// Generates hints that remove C/C++ functions.
//
// A single attempt (hint) is made for all definitions/declarations that share
// the same name; file/namespace/class scopes are ignored.
class FunctionRemover {
public:
  FunctionRemover();
  ~FunctionRemover();
  void processFile(const std::string &FileContents, TSTree &Tree);

private:
  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
};

#endif
