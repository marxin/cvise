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

#include "MoveDefinitionToDeclaration.h"

#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/ASTContext.h"
#include "clang/Basic/SourceManager.h"

#include "TransformationManager.h"

using namespace clang;

static const char *DescriptionMsg =
"Move definitions towards its declaration. \
Supporting functions, methods, variables, structs, unions and classes. \
Note that this pass could generate uncompilable code. \n";

static RegisterTransformation<MoveDefinitionToDeclaration>
         Trans("move-definition-to-declaration", DescriptionMsg);

class MoveDefinitionToDeclaration::CollectionVisitor : public RecursiveASTVisitor<CollectionVisitor> {
    MoveDefinitionToDeclaration* ConsumerInstance;

public:
  explicit CollectionVisitor(MoveDefinitionToDeclaration* Instance) : ConsumerInstance(Instance)
  { }

  void CheckAndAddCondidate(Decl* Def) {
    auto* Decl = Def->getPreviousDecl();
    if (Decl == nullptr || Def == Decl)
      return;
    if (ConsumerInstance->isInIncludedFile(Def) || ConsumerInstance->isInIncludedFile(Decl))
      return;

    ConsumerInstance->FunctionCandidates.push_back(Def);
  }

  bool VisitFunctionDecl(FunctionDecl* FD) {
    if (FD->isThisDeclarationADefinition())
      CheckAndAddCondidate(FD);

    return true;
  }

  bool VisitVarDecl(VarDecl* VD) {
    if (VD->isThisDeclarationADefinition())
      CheckAndAddCondidate(VD);

    return true;
  }

  bool VisitTagDecl(TagDecl* VD) {
    if (VD->isThisDeclarationADefinition())
      CheckAndAddCondidate(VD);

    return true;
  }

private:
};

void MoveDefinitionToDeclaration::HandleTranslationUnit(ASTContext &Ctx)
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
  TheFunctionDecl = TheFunctionDef->getPreviousDecl();

  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);

  TransAssert(TheFunctionDecl && "NULL TheFunctionDecl!");
  TransAssert(TheFunctionDef && "NULL TheFunctionDef!");

  doRewriting();

  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

// Decl::getDescribedTemplateParams was introduced in LLVM 11.
// Copied here for backwards compatibility.
static const TemplateParameterList* getDescribedTemplateParams(Decl* D) {
  if (auto* TD = D->getDescribedTemplate())
    return TD->getTemplateParameters();
  if (auto* CTPSD = dyn_cast<ClassTemplatePartialSpecializationDecl>(D))
    return CTPSD->getTemplateParameters();
  if (auto* VTPSD = dyn_cast<VarTemplatePartialSpecializationDecl>(D))
    return VTPSD->getTemplateParameters();
  return nullptr;
}

void MoveDefinitionToDeclaration::doRewriting(void)
{
  SourceRange DefRange = RewriteHelper->getDeclFullSourceRange(TheFunctionDef);

  // Remove namespace and class qualifiers
  if (auto* DD = dyn_cast<DeclaratorDecl>(TheFunctionDef)) {
    if (auto QL = DD->getQualifierLoc()) {
      TheRewriter.RemoveText(QL.getSourceRange());
    }
  }

  if (auto* MethDecl = dyn_cast<CXXMethodDecl>(TheFunctionDecl)) {
    auto* MethDef = cast<CXXMethodDecl>(TheFunctionDef);

    // Update the template parameters name of the class if they are empty
    // This is very likely since unused parameter names gets removed during reduction
    if (MethDef->getNumTemplateParameterLists() == 1) {
      TemplateParameterList* TPL = MethDef->getTemplateParameterList(0);

      if (const TemplateParameterList* ClassTPL = getDescribedTemplateParams(MethDecl->getParent())) {
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
    for (unsigned i = 0; i < MethDef->getNumTemplateParameterLists(); ++i) {
      TemplateParameterList* TPL = MethDef->getTemplateParameterList(i);
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
    RewriteHelper->addStringAfterDecl(TheFunctionDecl, FuncDefStr);
  }
}

MoveDefinitionToDeclaration::~MoveDefinitionToDeclaration(void)
{
  // Nothing to do
}
