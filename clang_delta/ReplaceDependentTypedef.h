//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef REPLACE_DEPENDENT_TYPEDEF_H
#define REPLACE_DEPENDENT_TYPEDEF_H

#include <string>
#include <vector>
#include "Transformation.h"

namespace clang {
  class DeclGroupRef;
  class ASTContext;
  class QualType;
  class Type;
  class TypedefNameDecl;
  class CXXRecordDecl;
}

namespace llvm {
  class StringRef;
}

class ReplaceDependentTypedefCollectionVisitor;

class ReplaceDependentTypedef : public Transformation {
friend class ReplaceDependentTypedefCollectionVisitor;

public:
  ReplaceDependentTypedef(const char *TransName, const char *Desc)
    : Transformation(TransName, Desc, /*MultipleRewrites=*/true),
      CollectionVisitor(NULL)
  {}

  ~ReplaceDependentTypedef();

private:
  struct Instance {
    std::string TheTyName;
    const clang::TypedefNameDecl *TheTypedefDecl = NULL;
    bool NeedTypenameKeyword = false;
  };

  virtual void Initialize(clang::ASTContext &context);

  virtual void HandleTranslationUnit(clang::ASTContext &Ctx);

  void handleOneTypedefDecl(const clang::TypedefNameDecl *D);

  bool isValidType(const clang::QualType &QT);

  void rewriteTypedefDecl(const Instance &Inst);

  ReplaceDependentTypedefCollectionVisitor *CollectionVisitor;

  // Unimplemented
  ReplaceDependentTypedef();

  ReplaceDependentTypedef(const ReplaceDependentTypedef &);

  void operator=(const ReplaceDependentTypedef &);

  std::vector<Instance> Instances;
};

#endif

