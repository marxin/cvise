//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef MOVE_DEFINITION_TO_DECLARATION_H
#define MOVE_DEFINITION_TO_DECLARATION_H

#include <string>
#include "llvm/ADT/DenseMap.h"
#include "Transformation.h"

namespace clang {
  class DeclGroupRef;
  class ASTContext;
  class FunctionDecl;
}

class MoveDefinitionToDeclaration : public Transformation {
  class CollectionVisitor;


public:

  MoveDefinitionToDeclaration(const char *TransName, const char *Desc)
    : Transformation(TransName, Desc)
  { }

  ~MoveDefinitionToDeclaration(void);

private:
  
  typedef llvm::DenseMap<clang::FunctionDecl *, clang::FunctionDecl *>
            FuncDeclToFuncDeclMap;

  virtual void HandleTranslationUnit(clang::ASTContext &Ctx);

  void doRewriting(void);

  std::vector<clang::Decl*> FunctionCandidates;

  clang::Decl* TheFunctionDecl = nullptr;

  clang::Decl* TheFunctionDef = nullptr;
};
#endif
