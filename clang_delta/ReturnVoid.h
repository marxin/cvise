//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef VOID_RETURN_H
#define VOID_RETURN_H

#include <optional>
#include <string>
#include "llvm/ADT/SmallVector.h"
#include "Transformation.h"

namespace clang {
  class DeclGroupRef;
  class ASTContext;
  class FunctionDecl;
  class ReturnStmt;
}

class RVASTVisitor;
class RVCollectionVisitor;
struct ClassifiedToken;

class ReturnVoid : public Transformation {
friend class RVASTVisitor;
friend class RVCollectionVisitor;

public:

  ReturnVoid(const char *TransName, const char *Desc)
    : Transformation(TransName, Desc),
      CollectionVisitor(NULL),
      TransformationASTVisitor(NULL),
      TheFuncDecl(NULL),
      FuncDefStartPos(NULL),
      FuncDefEndPos(NULL)
  { }

  ~ReturnVoid(void);

private:
  
  virtual void Initialize(clang::ASTContext &context);

  virtual void HandleTranslationUnit(clang::ASTContext &Ctx);

  void keepFuncDefRange(clang::FunctionDecl *FD);

  bool isNonVoidReturnFunction(clang::FunctionDecl *FD);

  bool isInTheFuncDef(clang::ReturnStmt *RS);

  llvm::Optional<llvm::SmallVector<ClassifiedToken, 8>>
    classifyTokensBeforeFunctionName(
      const clang::FunctionDecl& F, const clang::ASTContext& Ctx, const clang::SourceManager& SM,
      const clang::LangOptions& LangOpts);

  clang::SourceRange findReturnTypeAndCVSourceRange(
    const clang::FunctionDecl& F, const clang::TypeLoc& ReturnLoc, const clang::ASTContext& Ctx,
    const clang::SourceManager& SM, const clang::LangOptions& LangOpts);

  RVCollectionVisitor *CollectionVisitor;

  RVASTVisitor *TransformationASTVisitor;

  llvm::SmallVector<clang::FunctionDecl *, 10> ValidFuncDecls;

  clang::FunctionDecl *TheFuncDecl;

  const char *FuncDefStartPos;

  const char *FuncDefEndPos;

  // Unimplemented
  ReturnVoid(void);

  ReturnVoid(const ReturnVoid &);

  void operator=(const ReturnVoid &);
};
#endif
