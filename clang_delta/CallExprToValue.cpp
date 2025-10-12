//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2015, 2017, 2019 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "CallExprToValue.h"

#include <vector>

#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/ASTContext.h"
#include "clang/Basic/SourceManager.h"

#include "TransformationManager.h"

using namespace clang;

static const char *DescriptionMsg =
"Replace a call expression with a value or variable which \
has the same type as CallExpr's type. If CallExpr is type \
of integer/pointer, it will be replaced with 0. If it has \
type of union/struct, it will be replaced with a newly created \
global variable with a correct type. \n";

static RegisterTransformation<CallExprToValue>
         Trans("callexpr-to-value", DescriptionMsg);

class CallExprToValueVisitor : public
  RecursiveASTVisitor<CallExprToValueVisitor> {

public:

  explicit CallExprToValueVisitor(CallExprToValue *Instance)
    : ConsumerInstance(Instance),
      CurrentFD(NULL)
  { }

  bool VisitCallExpr(CallExpr *CE);

  bool VisitFunctionDecl(FunctionDecl *FD);

private:

  CallExprToValue *ConsumerInstance;

  const FunctionDecl *CurrentFD;
};

bool CallExprToValueVisitor::VisitCallExpr(CallExpr *CE)
{
  if (ConsumerInstance->isInIncludedFile(CE))
    return true;

  ConsumerInstance->Instances.push_back({CE, CurrentFD});
  return true;
}

bool CallExprToValueVisitor::VisitFunctionDecl(FunctionDecl *FD)
{
  // Note that CurrentFD could not be the function decl where TheCallExpr
  // shows up, e.g., we could have:
  // struct A {
  //   void foo();
  //   static int value = bar();
  // };
  CurrentFD = FD;
  return true;
}

void CallExprToValue::Initialize(ASTContext &context)
{
  Transformation::Initialize(context);
  CollectionVisitor = new CallExprToValueVisitor(this);
  NameQueryWrap =
    new TransNameQueryWrap(RewriteHelper->getTmpVarNamePrefix());
}

void CallExprToValue::HandleTranslationUnit(ASTContext &Ctx)
{
  CollectionVisitor->TraverseDecl(Ctx.getTranslationUnitDecl());
  ValidInstanceNum = static_cast<int>(Instances.size());

  if (QueryInstanceOnly)
    return;

  if (ToCounter != std::numeric_limits<int>::max() &&
      TransformationCounter > ValidInstanceNum) {
    TransError = TransMaxInstanceError;
    return;
  }

  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);

  NameQueryWrap->TraverseDecl(Ctx.getTranslationUnitDecl());
  NamePostfix = NameQueryWrap->getMaxNamePostfix() + 1;

  if (ToCounter == std::numeric_limits<int>::max()) {
    for (const auto &Inst : Instances)
      replaceCallExpr(Inst);
  } else {
    replaceCallExpr(Instances[TransformationCounter - 1]);
  }

  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

void CallExprToValue::replaceCallExpr(const Instance &Inst)
{
  auto HintScope = Hints->MakeHintScope();
  std::string CommaStr = "";

  QualType RVQualType = Inst.TheCallExpr->getType();
  const Type *RVType = RVQualType.getTypePtr();
  if (RVType->isVoidType()) {
    // Nothing to do
  }
  else if (RVType->isUnionType() || RVType->isStructureType()) {
    std::string RVStr("");
    RewriteHelper->getTmpTransName(NamePostfix, RVStr);
    NamePostfix++;

    CommaStr = RVStr;
    RVQualType.getAsStringInternal(RVStr, getPrintingPolicy());
    RVStr += ";\n";
    if (Inst.FD) {
      RewriteHelper->insertStringBeforeFunc(Inst.FD, RVStr);
    }
    else {
      SourceLocation InsLoc = Inst.TheCallExpr->getBeginLoc();
      Hints->AddPatch(SourceRange(InsLoc, InsLoc), RVStr);
      TheRewriter.InsertTextBefore(InsLoc, RVStr);
    }
  }
  else {
    CommaStr = "0";
  }

  RewriteHelper->replaceExpr(Inst.TheCallExpr, CommaStr);
}

CallExprToValue::~CallExprToValue(void)
{
  delete CollectionVisitor;
  delete NameQueryWrap;
}

