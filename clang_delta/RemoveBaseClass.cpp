//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2014, 2015, 2016, 2017, 2018 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "RemoveBaseClass.h"

#include "clang/AST/ASTContext.h"
#include "clang/Basic/SourceManager.h"
#include "CommonRenameClassRewriteVisitor.h"

#include "TransformationManager.h"

using namespace clang;
using namespace clang_delta_common_visitor;

static const char *DescriptionMsg = 
"This pass removes a base class from a derived class. \n";

// Note that this pass doesn't do much analysis, so
// it will produce quite a few uncompilable code, especially
// when multi-inheritance is involved.

static RegisterTransformation<RemoveBaseClass, RemoveBaseClass::EMode>
         Trans("remove-base-class", DescriptionMsg, RemoveBaseClass::EMode::Remove);

class RemoveBaseClassBaseVisitor : public 
  RecursiveASTVisitor<RemoveBaseClassBaseVisitor> {

public:
  explicit RemoveBaseClassBaseVisitor(
             RemoveBaseClass *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitCXXRecordDecl(CXXRecordDecl *CXXRD);

private:
  RemoveBaseClass *ConsumerInstance;
};

bool RemoveBaseClassBaseVisitor::VisitCXXRecordDecl(
       CXXRecordDecl *CXXRD)
{
  ConsumerInstance->handleOneCXXRecordDecl(CXXRD);
  return true;
}

void RemoveBaseClass::Initialize(ASTContext &context) 
{
  Transformation::Initialize(context);
  CollectionVisitor = new RemoveBaseClassBaseVisitor(this);
}

void RemoveBaseClass::HandleTranslationUnit(ASTContext &Ctx)
{
  if (TransformationManager::isCLangOpt() ||
      TransformationManager::isOpenCLLangOpt()) {
    ValidInstanceNum = 0;
  }
  else {
    CollectionVisitor->TraverseDecl(Ctx.getTranslationUnitDecl());
  }

  if (QueryInstanceOnly)
    return;

  if (TransformationCounter > ValidInstanceNum) {
    TransError = TransMaxInstanceError;
    return;
  }

  TransAssert(TheBaseClass && "TheBaseClass is NULL!");
  TransAssert(TheDerivedClass && "TheDerivedClass is NULL!");
  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);

  doRewrite();

  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

bool RemoveBaseClass::isDirectlyDerivedFrom(const CXXRecordDecl *SubC, 
                                            const CXXRecordDecl *Base)
{
  for (CXXRecordDecl::base_class_const_iterator I = SubC->bases_begin(),
       E = SubC->bases_end(); I != E; ++I) {
    if (I->getType()->isDependentType())
      continue;

    const RecordType *RT = I->getType()->getAs<RecordType>();
#if LLVM_VERSION_MAJOR < 22
    const CXXRecordDecl *BaseDecl = dyn_cast<CXXRecordDecl>(RT->getDecl());
#else
    const CXXRecordDecl *BaseDecl =
        dyn_cast<CXXRecordDecl>(RT->getOriginalDecl());
#endif
    if (Base->getCanonicalDecl() == BaseDecl->getCanonicalDecl())
      return true;
  }
  return false;
}

void RemoveBaseClass::handleOneCXXRecordDecl(const CXXRecordDecl *CXXRD)
{
  if (isSpecialRecordDecl(CXXRD) || !CXXRD->isThisDeclarationADefinition())
    return;

  for (const CXXBaseSpecifier& BS : CXXRD->bases()) {
    auto* Base = BS.getType()->getAsCXXRecordDecl();

    if (Base == nullptr)
      continue;
    if (Mode == EMode::Merge && getNumExplicitDecls(Base) > MaxNumDecls)
      continue;
    if (isInIncludedFile(Base))
      continue;

    ValidInstanceNum++;
    if (ValidInstanceNum == TransformationCounter) {
      TransAssert(Base->hasDefinition() && "Base class does not have any definition!");
      TheBaseClass = Base->getDefinition();
      TheDerivedClass = CXXRD;
    }
  }
}

void RemoveBaseClass::doRewrite(void)
{
  if (Mode == EMode::Merge)
    copyBaseClassDecls();
  removeBaseSpecifier();
  if (Mode == EMode::Merge)
    RewriteHelper->removeClassDecls(TheBaseClass);

  // ISSUE: I didn't handle Base initializer in a Ctor's initlist.
  //        * keeping it untouched is wrong, because delegating constructors 
  //        are only valid in c++11
  //        * naively removing the base initializer doesn't work in some cases,
  //        e.g., 
  //        class A { 
  //          A(A&) {}
  //          A &a;
  //        };
  //        class C : A {
  //          C(A &x) : A(x) {}
  //        };
  //        during transformation, removing A(x) will leave &a un-initialized.
  // I chose to simply delete the base initializer. Seemingly we will 
  // generate fewer incompilable code by doing so...
  removeBaseInitializer();
}

// ISSUE: directly copying decls could bring in name conflicts
void RemoveBaseClass::copyBaseClassDecls(void)
{
  if (!getNumExplicitDecls(TheBaseClass))
    return;

  std::string DeclsStr;
  auto* CTSD = dyn_cast<ClassTemplateSpecializationDecl>(TheBaseClass);
  if (CTSD && CTSD->getSpecializationKind() == TSK_ImplicitInstantiation) {
    // For template bases, we use the printing feature of clang to generate
    // the class with all resolved template parameters

    // Rename internally the constructors to the derived class
    for (CXXConstructorDecl* CD : CTSD->ctors()) {
      CD->setDeclName(TheDerivedClass->getDeclName());
    }

    llvm::raw_string_ostream Strm(DeclsStr);
    CTSD->print(Strm);

    DeclsStr.erase(0, DeclsStr.find('{') + 1);
    DeclsStr.erase(DeclsStr.rfind('}'), 1);
  } else {
    // Rename constructors
    for (CXXConstructorDecl* CD : TheBaseClass->ctors()) {
      TheRewriter.ReplaceText(CD->getNameInfo().getSourceRange(), TheDerivedClass->getDeclName().getAsString());
    }

    SourceLocation StartLoc = TheBaseClass->getBraceRange().getBegin();
    SourceLocation EndLoc = TheBaseClass->getBraceRange().getEnd();
    TransAssert(EndLoc.isValid() && "Invalid RBraceLoc!");
    StartLoc = StartLoc.getLocWithOffset(1);
    EndLoc = EndLoc.getLocWithOffset(-1);

    DeclsStr = TheRewriter.getRewrittenText(SourceRange(StartLoc, EndLoc)) + "\n";
  }

  TransAssert(!DeclsStr.empty() && "Empty DeclsStr!");
  SourceLocation InsertLoc = TheDerivedClass->getBraceRange().getEnd();
  TheRewriter.InsertTextBefore(InsertLoc, DeclsStr);
}

bool RemoveBaseClass::isTheBaseClass(const CXXBaseSpecifier &Specifier)
{
#if LLVM_VERSION_MAJOR < 22
  const Type *Ty = TheBaseClass->getTypeForDecl();
#else
  const Type *Ty = TheBaseClass->getASTContext()
                       .getCanonicalTagType(TheBaseClass)
                       ->getTypePtr();
#endif
  return Context->hasSameType(Specifier.getType(), 
                              Ty->getCanonicalTypeInternal());
}

void RemoveBaseClass::removeBaseSpecifier(void)
{
  unsigned NumBases = TheDerivedClass->getNumBases();
  TransAssert((NumBases >= 1) && "TheDerivedClass doesn't have any base!");
  if (NumBases == 1) {
    SourceLocation StartLoc = TheDerivedClass->getLocation();
    StartLoc = RewriteHelper->getLocationUntil(StartLoc, ':');
    SourceLocation EndLoc = RewriteHelper->getLocationUntil(StartLoc, '{');
    EndLoc = EndLoc.getLocWithOffset(-1);

    TheRewriter.RemoveText(SourceRange(StartLoc, EndLoc));
    return;
  }

  CXXRecordDecl::base_class_const_iterator I = TheDerivedClass->bases_begin();
  // remove 'Y,' in code like 'class X : public Y, Z {};'
  if (isTheBaseClass(*I)) {
    RewriteHelper->removeTextUntil((*I).getSourceRange(), ',');
    return;
  }

  ++I;
  CXXRecordDecl::base_class_const_iterator E = TheDerivedClass->bases_end();
  for (; I != E; ++I) {
    if (isTheBaseClass(*I)) {
      // remove ',Z' in code like 'class X : public Y, Z {};'
      SourceRange Range = (*I).getSourceRange();
      SourceLocation EndLoc = RewriteHelper->getEndLocationFromBegin(Range);
      RewriteHelper->removeTextFromLeftAt(Range, ',', EndLoc);
      return;
    }
  }
  TransAssert(0 && "Unreachable code!");
}

void RemoveBaseClass::rewriteOneCtor(const CXXConstructorDecl *Ctor)
{
  unsigned Idx = 0;
  const CXXCtorInitializer *Init = NULL;
  for (CXXConstructorDecl::init_const_iterator I = Ctor->init_begin(),
       E = Ctor->init_end(); I != E; ++I) {
    if (!(*I)->isWritten())
      continue;

    if ((*I)->isBaseInitializer()) {
      const Type *Ty = (*I)->getBaseClass();
      TransAssert(Ty && "Invalid Base Class Type!");
#if LLVM_VERSION_MAJOR < 22
      QualType CanonT =
          TheBaseClass->getTypeForDecl()->getCanonicalTypeInternal();
#else
      QualType CanonT = TheBaseClass->getASTContext()
                                   .getCanonicalTagType(TheBaseClass)
                                   ->getTypePtr()
                                   ->getCanonicalTypeInternal();
#endif
      if (Context->hasSameType(Ty->getCanonicalTypeInternal(), CanonT)) {
        Init = (*I);
        break;
      }
    }
    Idx++;
  }
  if (Init) {
    RewriteHelper->removeCXXCtorInitializer(Init, Idx,
                     getNumCtorWrittenInitializers(*Ctor));
  }
}

void RemoveBaseClass::removeBaseInitializer(void)
{
  for (Decl* D : TheDerivedClass->decls()) {
    if (auto* FTD = dyn_cast<FunctionTemplateDecl>(D))
      D =FTD->getTemplatedDecl();
    if (auto* Ctor = dyn_cast<CXXConstructorDecl>(D))
      if (Ctor->isThisDeclarationADefinition() && !Ctor->isDefaulted())
        rewriteOneCtor(Ctor);
  }
}

RemoveBaseClass::~RemoveBaseClass(void)
{
  delete CollectionVisitor;
}
