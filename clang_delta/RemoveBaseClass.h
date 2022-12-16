//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef REMOVE_BASE_CLASS_H
#define REMOVE_BASE_CLASS_H

#include "llvm/ADT/SmallPtrSet.h"
#include "Transformation.h"

namespace clang {
  class DeclGroupRef;
  class ASTContext;
  class CXXBaseSpecifier;
  class CXXConstructorDecl;
}

class RemoveBaseClassBaseVisitor;

class RemoveBaseClass : public Transformation {
friend class RemoveBaseClassBaseVisitor;

public:
  enum class EMode { Remove, Merge };

  RemoveBaseClass(const char *TransName, const char *Desc, EMode Mode)
    : Transformation(TransName, Desc),
      Mode(Mode)
  { }
  ~RemoveBaseClass(void);

private:
  typedef llvm::SmallPtrSet<const clang::CXXRecordDecl *, 20> CXXRecordDeclSet;

  virtual void Initialize(clang::ASTContext &context);

  virtual void HandleTranslationUnit(clang::ASTContext &Ctx);

  void handleOneCXXRecordDecl(const clang::CXXRecordDecl *CXXRD);

  void copyBaseClassDecls(void);

  void removeBaseSpecifier(void);

  void removeBaseInitializer(void);

  void rewriteOneCtor(const clang::CXXConstructorDecl *Ctor);

  bool isDirectlyDerivedFrom(const clang::CXXRecordDecl *SubC, 
                             const clang::CXXRecordDecl *Base);

  void doRewrite(void);

  bool isTheBaseClass(const clang::CXXBaseSpecifier &Specifier);

  RemoveBaseClassBaseVisitor *CollectionVisitor = nullptr;

  const clang::CXXRecordDecl *TheBaseClass = nullptr;

  const clang::CXXRecordDecl *TheDerivedClass = nullptr;

  const unsigned MaxNumDecls = 5;

  EMode Mode;

  // Unimplemented
  RemoveBaseClass(void);

  RemoveBaseClass(const RemoveBaseClass &);

  void operator=(const RemoveBaseClass &);
};

#endif

