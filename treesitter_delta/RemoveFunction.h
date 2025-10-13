#ifndef REMOVE_FUNCTION_H
#define REMOVE_FUNCTION_H

#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include <tree_sitter/api.h>

#include "Transformation.h"

// Generates hints that remove C/C++ functions.
//
// A single attempt (hint) is made for all definitions/declarations that share
// the same name; file/namespace/class scopes are ignored.
class FunctionRemover : public Transformation {
public:
  struct Instance {
    std::optional<int> PathId;
    uint32_t StartByte = 0;
    uint32_t EndByte = 0;

    bool operator<(const Instance &Other) const;
  };

  using NameToInstanceVec = std::map<std::string, std::vector<Instance>>;

  FunctionRemover();
  ~FunctionRemover() override;
  void processFile(const std::string &FileContents, TSTree &Tree,
                   std::optional<int> PathId) override;
  void finalize() override;

private:
  std::unique_ptr<TSQuery, decltype(&ts_query_delete)> Query;
  NameToInstanceVec InstancesByName;
};

#endif
