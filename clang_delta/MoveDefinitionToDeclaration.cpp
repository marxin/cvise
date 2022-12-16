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

    auto DefRange = ConsumerInstance->RewriteHelper->getDeclFullSourceRange(Def);
    auto DeclRange = ConsumerInstance->RewriteHelper->getDeclFullSourceRange(Decl);
    if (DefRange.isInvalid() || DeclRange.isInvalid() || ConsumerInstance->isInIncludedFile(DefRange) || ConsumerInstance->isInIncludedFile(DeclRange))
      return;

    auto Text = ConsumerInstance->TheRewriter.getRewrittenText({ DeclRange.getEnd(), DefRange.getBegin().getLocWithOffset(-1) });
    if (std::all_of(Text.begin(), Text.end(), isspace))
      return;

    ConsumerInstance->DefCandidates.push_back(Def);
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

  ValidInstanceNum = DefCandidates.size();

  if (QueryInstanceOnly)
    return;

  if (TransformationCounter > ValidInstanceNum) {
    TransError = TransMaxInstanceError;
    return;
  }

  TheDef = DefCandidates[TransformationCounter-1];
  TheDecl = TheDef->getPreviousDecl();

  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);

  TransAssert(TheDecl && "NULL TheDecl!");
  TransAssert(TheDef && "NULL TheDef!");

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
  SourceRange DefRange = RewriteHelper->getDeclFullSourceRange(TheDef);

  // Remove namespace and class qualifiers
  if (auto* DD = dyn_cast<DeclaratorDecl>(TheDef)) {
    if (auto QL = DD->getQualifierLoc()) {
      TheRewriter.RemoveText(QL.getSourceRange());
    }
  }

  if (auto* MethDecl = dyn_cast<CXXMethodDecl>(TheDecl)) {
    auto* MethDef = cast<CXXMethodDecl>(TheDef);

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
  if (isa<CXXMethodDecl>(TheDecl)) {
    auto DeclRange = RewriteHelper->getDeclFullSourceRange(TheDecl);
    TheRewriter.ReplaceText(DeclRange, FuncDefStr);
  } else {
    RewriteHelper->addStringAfterDecl(TheDecl, FuncDefStr);
  }
}

MoveDefinitionToDeclaration::~MoveDefinitionToDeclaration(void)
{
  // Nothing to do
}
