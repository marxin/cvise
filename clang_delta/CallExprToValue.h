//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef CALL_EXPR_TO_VALUE_H
#define CALL_EXPR_TO_VALUE_H

#include <string>
#include <vector>
#include "Transformation.h"

namespace clang {
  class DeclGroupRef;
  class ASTContext;
  class FunctionDecl;
  class CallExpr;
  class Expr;
}

class CallExprToValueVisitor;

class CallExprToValue : public Transformation {
friend class CallExprToValueVisitor;

public:

  CallExprToValue(const char *TransName, const char *Desc)
    : Transformation(TransName, Desc, /*MultipleRewrites=*/true),
      CollectionVisitor(NULL),
      NameQueryWrap(NULL),
      CurrentFD(NULL),
      NamePostfix(0)
  { }

  ~CallExprToValue(void);

private:
  struct Instance {
    const clang::CallExpr *TheCallExpr;
    const clang::FunctionDecl *FD;
  };

  virtual void Initialize(clang::ASTContext &context);

  virtual void HandleTranslationUnit(clang::ASTContext &Ctx);

  void handleOneArgStr(const clang::Expr *Arg, std::string &Str);

  void replaceCallExpr(const Instance &Inst);

  CallExprToValueVisitor *CollectionVisitor;

  TransNameQueryWrap *NameQueryWrap;

  const clang::FunctionDecl *CurrentFD;

  std::vector<Instance> Instances;

  unsigned int NamePostfix;

  // Unimplemented
  CallExprToValue(void);

  CallExprToValue(const CallExprToValue &);

  void operator=(const CallExprToValue &);
};
#endif
