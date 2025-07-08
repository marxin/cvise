//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2014, 2015, 2016, 2018, 2019 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef HINTS_BUILDER_H
#define HINTS_BUILDER_H

#include <stdint.h>

#include <optional>
#include <string>
#include <vector>

#include "clang/Basic/LangOptions.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Rewrite/Core/Rewriter.h"
#include "llvm/ADT/StringRef.h"

// Helper for generating reduction hints - for the background and data format,
// see //cvise/utils/hint.py.
//
// Intended usage for generating a hint (with one or multiple patches):
//
//   {
//     auto Scope = Builder.MakeHintScope();
//     Builder.AddPatch(...);
//     Builder.AddPatch(...);
//     ...
//   }
//
// Use the Get...Json[s]() methods to obtain the built hints for serialization.
class HintsBuilder {
public:
  class [[nodiscard]] HintScope {
  public:
    ~HintScope();
    HintScope(const HintScope&) = delete;
    HintScope& operator=(const HintScope&) = delete;

  private:
    friend class HintsBuilder;

    explicit HintScope(HintsBuilder &B);

    HintsBuilder &Builder;
  };

  HintsBuilder(clang::SourceManager &SM, const clang::LangOptions &LO);
  ~HintsBuilder();

  HintScope MakeHintScope();

  void AddPatch(clang::SourceRange R, const std::string &Replacement = "");
  void AddPatch(clang::CharSourceRange R, const std::string &Replacement = "");
  void AddPatch(clang::SourceLocation L, int64_t Len,
                const std::string &Replacement = "");

  void ReverseOrder();

  std::string GetVocabularyJson() const;
  std::vector<std::string> GetHintJsons() const;

private:
  struct Patch {
    int64_t L, R;
    std::optional<int64_t> V;
  };

  struct Hint {
    std::vector<Patch> Patches;
  };

  void FinishCurrentHint();
  int64_t LookupOrCreateVocabId(const std::string &S);

  clang::SourceManager &SourceMgr;
  // Used to measure token sizes. It's a separate object from
  // `Transformation::TheRewriter`, because the source locations change in the
  // latter as rewrites go.
  const clang::Rewriter NoOpRewriter;
  std::vector<std::string> Vocab;
  std::vector<Hint> Hints;
  Hint CurrentHint;
};

#endif
