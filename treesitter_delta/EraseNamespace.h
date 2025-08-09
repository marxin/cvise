#ifndef ERASE_NAMESPACE_H
#define ERASE_NAMESPACE_H

#include <memory>
#include <string>

#include <tree_sitter/api.h>

// Emits hints that deletes contents inside C++ namespaces.
//
// Attempts erasing all occurrences of a namespace with the given name at once
// (assuming that they are intertwined, like one namespace definition containing
// a class definition and another containing this class' methods).
class NamespaceEraser {
public:
  NamespaceEraser();
  ~NamespaceEraser();
  void processFile(const std::string &FileContents, TSTree &Tree);

private:
  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
};

#endif
