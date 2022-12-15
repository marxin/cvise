//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef MOVE_FUNCTION_BODY_H
#define MOVE_FUNCTION_BODY_H

#include <string>
#include "llvm/ADT/DenseMap.h"
#include "Transformation.h"

namespace clang {
  class DeclGroupRef;
  class ASTContext;
  class FunctionDecl;
}

class MoveFunctionBody : public Transformation {
  class CollectionVisitor;


public:

  MoveFunctionBody(const char *TransName, const char *Desc)
    : Transformation(TransName, Desc)
  { }

  ~MoveFunctionBody(void);

private:
  
  typedef llvm::DenseMap<clang::FunctionDecl *, clang::FunctionDecl *>
            FuncDeclToFuncDeclMap;

  virtual void HandleTranslationUnit(clang::ASTContext &Ctx);

  void doRewriting(void);

  std::vector<clang::FunctionDecl*> FunctionCandidates;

  clang::FunctionDecl *TheFunctionDecl = nullptr;

  clang::FunctionDecl *TheFunctionDef = nullptr;
};
#endif
