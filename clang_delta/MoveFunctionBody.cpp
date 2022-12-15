//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2015 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "MoveFunctionBody.h"

#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/ASTContext.h"
#include "clang/Basic/SourceManager.h"

#include "TransformationManager.h"

using namespace clang;

static const char *DescriptionMsg =
"Move function body towards its declaration. \
Note that this pass would generate uncompilable code. \n";

static RegisterTransformation<MoveFunctionBody>
         Trans("move-function-body", DescriptionMsg);

class MoveFunctionBody::CollectionVisitor : public RecursiveASTVisitor<CollectionVisitor> {
    MoveFunctionBody* ConsumerInstance;

public:
  explicit CollectionVisitor(MoveFunctionBody* Instance) : ConsumerInstance(Instance)
  { }

  bool VisitFunctionDecl(FunctionDecl* FuncDef) {
    if (!FuncDef->isThisDeclarationADefinition())
      return true;

    auto* FuncDecl = FuncDef->getFirstDecl();
    if (FuncDef == FuncDecl)
      return true;
    if (ConsumerInstance->isInIncludedFile(FuncDef) || ConsumerInstance->isInIncludedFile(FuncDecl))
      return true;

    ConsumerInstance->FunctionCandidates.push_back(FuncDef);

    return true;
  }

private:
};

void MoveFunctionBody::HandleTranslationUnit(ASTContext &Ctx)
{
  CollectionVisitor(this).TraverseDecl(Ctx.getTranslationUnitDecl());

  ValidInstanceNum = FunctionCandidates.size();

  if (QueryInstanceOnly)
    return;

  if (TransformationCounter > ValidInstanceNum) {
    TransError = TransMaxInstanceError;
    return;
  }

  TheFunctionDef = FunctionCandidates[TransformationCounter-1];
  TheFunctionDecl = TheFunctionDef->getFirstDecl();

  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);

  TransAssert(TheFunctionDecl && "NULL TheFunctionDecl!");
  TransAssert(!TheFunctionDecl->isThisDeclarationADefinition() &&
              "Invalid Function Declaration!");
  TransAssert(TheFunctionDef && "NULL TheFunctionDef!");
  TransAssert(TheFunctionDef->isThisDeclarationADefinition() &&
              "Invalid Function Definition!");

  doRewriting();

  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

// Needed for backwards compatibility. Copyied from Decl::getDescribedTemplateParams.
static const TemplateParameterList* getDescribedTemplateParams(Decl* D) {
  if (auto* TD = D->getDescribedTemplate())
    return TD->getTemplateParameters();
  if (auto* CTPSD = dyn_cast<ClassTemplatePartialSpecializationDecl>(D))
    return CTPSD->getTemplateParameters();
  if (auto* VTPSD = dyn_cast<VarTemplatePartialSpecializationDecl>(D))
    return VTPSD->getTemplateParameters();
  return nullptr;
}

void MoveFunctionBody::doRewriting(void)
{
  SourceRange DefRange = RewriteHelper->getDeclFullSourceRange(TheFunctionDef);

  // Remove namespace and class qualifiers
  if (auto QL = TheFunctionDef->getQualifierLoc()) {
    TheRewriter.RemoveText(QL.getSourceRange());
  }

  if (auto* MD = dyn_cast<CXXMethodDecl>(TheFunctionDecl)) {
    // Update the template parameters name of the class if they are empty
    // This is very likely since unused parameter names gets removed during reduction
    if (TheFunctionDef->getNumTemplateParameterLists() == 1) {
      TemplateParameterList* TPL = TheFunctionDef->getTemplateParameterList(0);

      if (const TemplateParameterList* ClassTPL = getDescribedTemplateParams(MD->getParent())) {
        assert(TPL->size() == ClassTPL->size());
        for (unsigned i2 = 0; i2 < ClassTPL->size(); ++i2) {
          auto* Param = TPL->getParam(i2);
          auto* ClassParam = ClassTPL->getParam(i2);

          if (ClassParam->getName().empty()) {
            std::string ParamStr = TheRewriter.getRewrittenText(Param->getSourceRange());
            TheRewriter.ReplaceText(ClassParam->getSourceRange().getEnd(), ParamStr);
          }
        }
      }

      TheRewriter.RemoveText(TPL->getSourceRange());
    }

    // Removing template lists for classes
    for (unsigned i = 0; i < TheFunctionDef->getNumTemplateParameterLists(); ++i) {
      TemplateParameterList* TPL = TheFunctionDef->getTemplateParameterList(i);
      TheRewriter.RemoveText(TPL->getSourceRange());
    }
  }

  std::string FuncDefStr = TheRewriter.getRewrittenText(DefRange);

  TheRewriter.RemoveText(DefRange);

  // Inside a class we need to remove the declaration
  if (isa<CXXMethodDecl>(TheFunctionDecl)) {
    auto DeclRange = RewriteHelper->getDeclFullSourceRange(TheFunctionDecl);
    TheRewriter.ReplaceText(DeclRange, FuncDefStr);
  } else {
    RewriteHelper->addStringAfterFuncDecl(TheFunctionDecl, FuncDefStr);
  }
}

MoveFunctionBody::~MoveFunctionBody(void)
{
  // Nothing to do
}
