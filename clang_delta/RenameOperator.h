//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef RENAME_OPERATOR_H
#define RENAME_OPERATOR_H

#include <string>
#include <set>
#include "llvm/ADT/DenseMap.h"
#include "Transformation.h"

namespace clang {
  class DeclGroupRef;
  class ASTContext;
  class FunctionDecl;
}

class RenameOperator : public Transformation {
  class CollectionVisitor;
  class RenameOperatorVisitor;

public:

  RenameOperator(const char *TransName, const char *Desc)
    : Transformation(TransName, Desc)
  { }

  virtual bool skipCounter(void) {
    return true;
  }

private:
  
  virtual void Initialize(clang::ASTContext &context);

  virtual void HandleTranslationUnit(clang::ASTContext &Ctx);

  void addFun(const clang::FunctionDecl *FD);

  std::string getNextFuncName();

  std::set<const clang::FunctionDecl*> FunctionSet;

  std::vector<const clang::FunctionDecl*> FunctionList;

  std::map<const clang::FunctionDecl*, std::string> RenameFunc;

  std::set<std::string> UsedNames;

  const std::string FunNamePrefix = "op";

  int NextFunNo = 1;
};
#endif
