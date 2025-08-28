#ifndef TRANSFORMATION_H
#define TRANSFORMATION_H

#include <optional>
#include <string>
#include <vector>

#include <tree_sitter/api.h>

// Base class for a heuristic transformation.
class Transformation {
public:
  virtual ~Transformation() = default;

  // Should return the static list of strings needed by hints.
  virtual std::vector<std::string> getVocabulary() const { return {}; }
  // Handle an input file and, when appropriate, emit hints.
  virtual void processFile(const std::string &FileContents, TSTree &Tree,
                           std::optional<int> FileId) = 0;
  // Called after all processFile() invocations - can be used to emit additional
  // hints.
  virtual void finalize() {}
};

#endif
