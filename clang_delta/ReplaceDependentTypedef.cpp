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

#include "ReplaceDependentTypedef.h"

#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/ASTContext.h"
#include "clang/Basic/SourceManager.h"

#include "TransformationManager.h"

using namespace clang;

static const char *DescriptionMsg =
"This pass replaces typedef names with the underlying type if the \
underlying type is dependent, e.g.: \n\
\n\
  template <class T> struct S { typedef T type; }; \n\
  struct A { }; \n\
  struct B { typedef S<A>::type type; }; \n\
==> \n\
  template <class T> struct S { typedef T type; }; \n\
  struct A { }; \n\
  struct B { typedef A type; }; \n\
\n\
It also tries to reduce the typedef chain, e.g. \n\
  typedef long xx_t; \n\
  typedef xx_t xx; \n\
==> \n\
  typedef long xx_t; \n\
  typedef long xx; \n\
";

static RegisterTransformation<ReplaceDependentTypedef>
         Trans("replace-dependent-typedef", DescriptionMsg);

static bool DependsOnTypedef(const Type &Ty) {
  switch (Ty.getTypeClass()) {
  case Type::SubstTemplateTypeParm: {
    const SubstTemplateTypeParmType *TP =
      dyn_cast<SubstTemplateTypeParmType>(&Ty);
    const Type *ReplTy = TP->getReplacementType().getTypePtr();
    return DependsOnTypedef(*ReplTy);
  }

#if LLVM_VERSION_MAJOR < 22
  case Type::Elaborated: {
    const ElaboratedType *ETy = dyn_cast<ElaboratedType>(&Ty);
    const Type *NamedTy = ETy->getNamedType().getTypePtr();
    return DependsOnTypedef(*NamedTy);
  }
#endif

  case Type::Typedef: {
    return true;
  }

  case Type::DependentName: {
    const DependentNameType *DNT = dyn_cast<DependentNameType>(&Ty);
#if LLVM_VERSION_MAJOR < 22
    const NestedNameSpecifier *Specifier = DNT->getQualifier();
    if (!Specifier)
      return false;
    const Type *NestedTy = Specifier->getAsType();
#else
    const NestedNameSpecifier Specifier = DNT->getQualifier();
    if (!Specifier)
      return false;
    const Type *NestedTy = Specifier.getAsType();
#endif
    if (!NestedTy)
      return false;
    return DependsOnTypedef(*NestedTy);
  }

  case Type::Record:
  case Type::Builtin: { // fall-through
    return false;
  }

  default:
    return false;
  }

  TransAssert(0 && "Unreachable code!");
  return false;
}

class ReplaceDependentTypedefCollectionVisitor : public
  RecursiveASTVisitor<ReplaceDependentTypedefCollectionVisitor> {

public:
  explicit
  ReplaceDependentTypedefCollectionVisitor(ReplaceDependentTypedef *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitTypedefNameDecl(TypedefNameDecl *D);

private:
  ReplaceDependentTypedef *ConsumerInstance;

};

bool
ReplaceDependentTypedefCollectionVisitor::VisitTypedefNameDecl(TypedefNameDecl *D)
{
  ConsumerInstance->handleOneTypedefDecl(D);
  return true;
}

void ReplaceDependentTypedef::Initialize(ASTContext &context)
{
  Transformation::Initialize(context);
  CollectionVisitor = new ReplaceDependentTypedefCollectionVisitor(this);
}

void ReplaceDependentTypedef::HandleTranslationUnit(ASTContext &Ctx)
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

  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);
  rewriteTypedefDecl();

  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

bool ReplaceDependentTypedef::isValidType(const QualType &QT)
{
  const Type *Ty = QT.getTypePtr();
  Type::TypeClass TC = Ty->getTypeClass();

  switch (TC) {
  case Type::SubstTemplateTypeParm:
  case Type::Typedef:
  case Type::DependentName: // fall-through
    return true;

#if LLVM_VERSION_MAJOR < 22
  case Type::Elaborated: {
    const ElaboratedType *ETy = dyn_cast<ElaboratedType>(Ty);
    ElaboratedTypeKeyword Keyword = ETy->getKeyword();

#if LLVM_VERSION_MAJOR >= 18
    return ((Keyword == ElaboratedTypeKeyword::Typename) || (Keyword == ElaboratedTypeKeyword::None));
#else
    return ((Keyword == ETK_Typename) || (Keyword == ETK_None));
#endif
  }
#endif

  default:
    return false;
  }

  TransAssert(0 && "Unreachable code!");
  return false;
}

void ReplaceDependentTypedef::handleOneTypedefDecl(const TypedefNameDecl *D)
{
  if (isInIncludedFile(D) || D->getBeginLoc().isInvalid())
    return;

  if (!isValidType(D->getUnderlyingType()))
    return;
  if (!DependsOnTypedef(*D->getUnderlyingType()))
    return;

  std::string Str = "";
  bool Typename = false;
  if (!getTypeString(D->getUnderlyingType(), Str, Typename))
    return;
  std::string TdefTyStr = "";
  D->getUnderlyingType().getAsStringInternal(
    TdefTyStr, getPrintingPolicy());
  if (Str == TdefTyStr)
    return;

  ValidInstanceNum++;
  if (ValidInstanceNum == TransformationCounter) {
    TheTypedefDecl = D;
    TheTyName = Str;
    NeedTypenameKeyword = Typename;
  }
}

void ReplaceDependentTypedef::rewriteTypedefDecl()
{
  std::string NewStr = "typedef ";
  if (NeedTypenameKeyword)
    NewStr += "typename ";
  NewStr = NewStr + TheTyName + " " + TheTypedefDecl->getNameAsString();
  SourceRange Range = TheTypedefDecl->getSourceRange();
  TheRewriter.ReplaceText(Range, NewStr);
}

ReplaceDependentTypedef::~ReplaceDependentTypedef()
{
  delete CollectionVisitor;
}

