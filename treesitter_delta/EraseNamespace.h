#ifndef ERASE_NAMESPACE_H
#define ERASE_NAMESPACE_H

#include <memory>
#include <string>

#include <tree_sitter/api.h>

// Emits hints that delete contents inside C++ namespaces.
class NamespaceEraser {
public:
  NamespaceEraser();
  ~NamespaceEraser();
  void processFile(const std::string &FileContents, TSTree &Tree);

private:
  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
};

#endif
