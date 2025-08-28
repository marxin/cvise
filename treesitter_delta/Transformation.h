#ifndef TRANSFORMATION_H
#define TRANSFORMATION_H

#include <optional>
#include <string>
#include <vector>

#include <tree_sitter/api.h>

class Transformation {
public:
  virtual ~Transformation() = default;

  virtual std::vector<std::string> getVocabulary() const { return {}; }
  virtual void processFile(const std::string &FileContents, TSTree &Tree,
                           std::optional<int> FileId) = 0;
  virtual void finalize() {}
};

#endif
