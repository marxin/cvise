//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2015, 2016, 2017, 2019 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "ClassToStruct.h"

#include "clang/Basic/SourceManager.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/ASTContext.h"
#include "clang/Lex/Lexer.h"

#include "TransformationManager.h"

using namespace clang;

static const char *DescriptionMsg = 
"The pass replaces class with struct keyword. \n";

static RegisterTransformation<ClassToStruct>
         Trans("class-to-struct", DescriptionMsg);

class ClassToStructVisitor : public 
  RecursiveASTVisitor<ClassToStructVisitor> {

public:
  explicit ClassToStructVisitor(
             ClassToStruct *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitCXXRecordDecl(CXXRecordDecl *CXXRD);

private:
  ClassToStruct *ConsumerInstance;
};

bool ClassToStructVisitor::VisitCXXRecordDecl(
       CXXRecordDecl *CXXRD)
{
  if (!CXXRD->isClass())
    return true;
  ConsumerInstance->CXXRDDefSet.insert(CXXRD->getDefinition());
  return true;
}

void ClassToStruct::Initialize(ASTContext &context) 
{
  Transformation::Initialize(context);
  CollectionVisitor = new ClassToStructVisitor(this);
}

void ClassToStruct::HandleTranslationUnit(ASTContext &Ctx)
{
  if (TransformationManager::isCLangOpt() ||
      TransformationManager::isOpenCLLangOpt()) {
    ValidInstanceNum = 0;
  }
  else {
    CollectionVisitor->TraverseDecl(Ctx.getTranslationUnitDecl());
    analyzeCXXRDSet();
  }

  if (QueryInstanceOnly)
    return;

  if (TransformationCounter > ValidInstanceNum) {
    TransError = TransMaxInstanceError;
    return;
  }

  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);
  replaceClassWithStruct();

  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

void ClassToStruct::analyzeCXXRDSet()
{
  for (CXXRecordDeclSetVector::iterator I = CXXRDDefSet.begin(), 
       E = CXXRDDefSet.end(); I != E; ++I) {
    const CXXRecordDecl *Def = (*I);
    ValidInstanceNum++;
    if (ValidInstanceNum == TransformationCounter)
      TheCXXRDDef = Def;
  }
}

void ClassToStruct::replaceClassWithStruct()
{
  TransAssert(TheCXXRDDef && "NULL Base CXXRD!");
  SourceLocation LocStart = TheCXXRDDef->getBeginLoc();
  SourceLocation LocEnd = LocStart.getLocWithOffset(strlen("class"));
  TransAssert(LocEnd.isValid() && "Invalid Location!");
  TheRewriter.ReplaceText(SourceRange(LocStart, LocEnd), "struct");
}

ClassToStruct::~ClassToStruct(void)
{
  delete CollectionVisitor;
}

