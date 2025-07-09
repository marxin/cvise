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

#include <string>
#include <vector>

#include "clang/Basic/LangOptions.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Rewrite/Core/Rewriter.h"
#include "llvm/ADT/StringRef.h"

// Helper for generating reduction hints - for the background and data format,
// see //cvise/utils/hint.py.
class HintsBuilder {
public:
  HintsBuilder(clang::SourceManager &SM, const clang::LangOptions &LO);
  ~HintsBuilder();

  void AddPatch(clang::SourceRange R);
  void AddPatch(clang::CharSourceRange R);
  void AddPatch(clang::SourceLocation L, int64_t Len);

  void FinishCurrentHint();

  void ReverseOrder();

  std::string GetVocabularyJson() const;
  std::vector<std::string> GetHintJsons() const;

private:
  struct Patch {
    int64_t L, R;
  };

  struct Hint {
    std::vector<Patch> Patches;
  };

  clang::SourceManager &SourceMgr;
  // Used to measure token sizes. It's a separate object from
  // `Transformation::TheRewriter`, because the source locations change in the
  // latter as rewrites go.
  const clang::Rewriter NoOpRewriter;
  std::vector<Hint> Hints;
  Hint CurrentHint;
};

#endif
