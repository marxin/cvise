//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2016 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef CLASS_TO_STRUCT_H
#define CLASS_TO_STRUCT_H

#include "llvm/ADT/SetVector.h"
#include "llvm/ADT/SmallPtrSet.h"
#include "Transformation.h"

namespace clang {
  class DeclGroupRef;
  class ASTContext;
  class CXXRecordDecl;
}

class ClassToStructVisitor;

class ClassToStruct : public Transformation {
friend class ClassToStructVisitor;

public:
  ClassToStruct(const char *TransName, const char *Desc)
    : Transformation(TransName, Desc),
      CollectionVisitor(NULL),
      TheCXXRDDef(NULL)
  { }

  ~ClassToStruct(void);

private:
  typedef llvm::SmallPtrSet<const clang::CXXRecordDecl *, 10> CXXRecordDeclSet;
  typedef llvm::SetVector<const clang::CXXRecordDecl *> CXXRecordDeclSetVector;

  virtual void Initialize(clang::ASTContext &context);

  virtual void HandleTranslationUnit(clang::ASTContext &Ctx);

  void analyzeCXXRDSet();

  void replaceClassWithStruct();

  CXXRecordDeclSetVector CXXRDDefSet;

  ClassToStructVisitor *CollectionVisitor;

  const clang::CXXRecordDecl *TheCXXRDDef;

  // Unimplemented
  ClassToStruct(void);

  ClassToStruct(const ClassToStruct &);

  void operator=(const ClassToStruct &);
};

#endif

