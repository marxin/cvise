#ifndef ERASE_NAMESPACE_H
#define ERASE_NAMESPACE_H

#include <memory>
#include <optional>
#include <string>

#include <tree_sitter/api.h>

#include "Transformation.h"

// Emits hints that delete contents inside C++ namespaces.
class NamespaceEraser : public Transformation {
public:
  NamespaceEraser();
  ~NamespaceEraser() override;
  std::vector<std::string> getVocabulary() const override;
  void processFile(const std::string &FileContents, TSTree &Tree,
                   std::optional<int> FileId) override;

private:
  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
};

#endif
