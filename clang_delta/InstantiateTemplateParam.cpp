//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2015, 2017, 2019, 2020 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "InstantiateTemplateParam.h"

#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/ASTContext.h"
#include "clang/Basic/SourceManager.h"

#include "TransformationManager.h"

using namespace clang;

static const char *DescriptionMsg = 
"This pass tries to instantiate a template parameter with  \
its actual argument if this parameter has been instantiated \n\
only once. \n";

static RegisterTransformation<InstantiateTemplateParam>
         Trans("instantiate-template-param", DescriptionMsg);

namespace {

typedef llvm::SmallPtrSet<const NamedDecl *, 8> TemplateParameterSet;

class TemplateParameterVisitor : public 
  RecursiveASTVisitor<TemplateParameterVisitor> {

public:
  explicit TemplateParameterVisitor(TemplateParameterSet &Params)
             : UsedParameters(Params) 
  { }

  ~TemplateParameterVisitor() { };

  bool VisitTemplateTypeParmTypeLoc(TemplateTypeParmTypeLoc Loc);

private:

  TemplateParameterSet &UsedParameters;
};

// seems clang can't detect the T in T::* in the following case:
// struct B;
// template <typename T> struct C {
//   C(void (T::*)()) { }
// };
// struct D { C<B> m; };
bool TemplateParameterVisitor::VisitTemplateTypeParmTypeLoc(
       TemplateTypeParmTypeLoc Loc)
{
  const TemplateTypeParmDecl *D = Loc.getDecl();
  UsedParameters.insert(D);
  return true;
}

} // end anonymous namespace

class InstantiateTemplateParamASTVisitor : public 
  RecursiveASTVisitor<InstantiateTemplateParamASTVisitor> {

public:
  explicit InstantiateTemplateParamASTVisitor(
             InstantiateTemplateParam *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitRecordDecl(RecordDecl *D);

  bool VisitClassTemplateDecl(ClassTemplateDecl *D);

  bool VisitFunctionTemplateDecl(FunctionTemplateDecl *D);

private:
  InstantiateTemplateParam *ConsumerInstance;

};

bool InstantiateTemplateParamASTVisitor::VisitRecordDecl(RecordDecl *D)
{
  ConsumerInstance->AvailableRecordDecls.insert(
    dyn_cast<RecordDecl>(D->getCanonicalDecl()));
  return true;
}

bool InstantiateTemplateParamASTVisitor::VisitClassTemplateDecl(
       ClassTemplateDecl *D)
{
  if (D->isThisDeclarationADefinition())
    ConsumerInstance->handleOneClassTemplateDecl(D);
  return true;
}

bool InstantiateTemplateParamASTVisitor::VisitFunctionTemplateDecl(
       FunctionTemplateDecl *D)
{
  if (D->isFirstDecl())
    ConsumerInstance->handleOneFunctionTemplateDecl(D);
  return true;
}

class InstantiateTemplateParamRewriteVisitor : public 
  RecursiveASTVisitor<InstantiateTemplateParamRewriteVisitor> {

public:
  explicit InstantiateTemplateParamRewriteVisitor(
             InstantiateTemplateParam *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitTemplateTypeParmTypeLoc(TemplateTypeParmTypeLoc Loc);

  bool VisitDeclRefExpr(DeclRefExpr* DRE) {
    if (DRE->getDecl() == ConsumerInstance->TheTemplateSpec) {
      auto Idx = ConsumerInstance->TheParameterIdx;
      if (DRE->getNumTemplateArgs() > Idx) {
        return ConsumerInstance->RewriteHelper->removeTemplateArgument(DRE, Idx);
      }
    }

    return true;
  }

private:
  InstantiateTemplateParam *ConsumerInstance;

};

bool 
InstantiateTemplateParamRewriteVisitor::VisitTemplateTypeParmTypeLoc(
       TemplateTypeParmTypeLoc Loc)
{
  const TemplateTypeParmDecl *D = Loc.getDecl();
  if (D != ConsumerInstance->TheParameter)
    return true;

  // I know it's ugly, but seems sometimes Clang injects some extra
  // TypeLoc which causes the problem, for example, in the code below,
  // template<typename T> class A {
  // public:
  // template<typename T1> struct C { typedef A other; };
  // };
  // template<typename T1, typename T2> class B {
  //   typedef typename T2::template C<int>::other type;
  // };
  // class B<char, A<char> >;
  // the "typedef typename T2 ..." is treated as 
  //   typedef typename T2::template T2::C<int>::other type;
  // where the second T2 is injected by Clang
  void *Ptr = Loc.getBeginLoc().getPtrEncoding();
  if (ConsumerInstance->VisitedLocs.count(Ptr))
    return true;
  ConsumerInstance->VisitedLocs.insert(Ptr);

  SourceRange Range = Loc.getSourceRange();
  ConsumerInstance->TheRewriter.ReplaceText(Range, 
                       ConsumerInstance->TheInstantiationString);
  return true;
}

class InstantiateTemplateParam::FindForwardDeclVisitor : public RecursiveASTVisitor<FindForwardDeclVisitor> {
  InstantiateTemplateParam* ConsumerInstance;
  std::string& ForwardStr;
  RecordDeclSet TempAvailableRecordDecls;
public:
  explicit FindForwardDeclVisitor(InstantiateTemplateParam* ConsumerInstance, std::string& ForwardStr) 
      : ConsumerInstance(ConsumerInstance), ForwardStr(ForwardStr)
  { }

  bool VisitRecordType(RecordType* RT) {
    ConsumerInstance->getForwardDeclStr(RT, ForwardStr, TempAvailableRecordDecls);
    return true;
  }
};

void InstantiateTemplateParam::Initialize(ASTContext &context) 
{
  Transformation::Initialize(context);
  CollectionVisitor = new InstantiateTemplateParamASTVisitor(this);
  ParamRewriteVisitor = new InstantiateTemplateParamRewriteVisitor(this);
}

void InstantiateTemplateParam::HandleTranslationUnit(ASTContext &Ctx)
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
  TransAssert(TheParameter && "NULL TheParameter!");
  TransAssert((TheInstantiationString != "") && "Invalid InstantiationString!");
  TransAssert(ParamRewriteVisitor && "NULL ParamRewriteVisitor!");
  ParamRewriteVisitor->TraverseDecl(Ctx.getTranslationUnitDecl());
  removeTemplateKeyword();
  addForwardDecl();

  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

void InstantiateTemplateParam::removeTemplateKeyword()
{
  if (isa<ClassTemplateDecl>(TheTemplateDecl))
    return;
  TemplateParameterList *TPList = TheTemplateDecl->getTemplateParameters();
  if (TheParameterIdx < TPList->size())
    RewriteHelper->removeTemplateParameter(TPList, TheParameterIdx);
}

void InstantiateTemplateParam::addForwardDecl()
{
  TransAssert(TheTemplateDecl && "NULL TheTemplateDecl!");
  if (TheForwardDeclString == "")
    return;
  RewriteHelper->insertStringBeforeTemplateDecl(TheTemplateDecl, 
                                                TheForwardDeclString);
}

void InstantiateTemplateParam::addOneForwardDeclStr(
       const RecordDecl *RD,
       std::string &ForwardStr,
       RecordDeclSet &TempAvailableRecordDecls)
{
  const RecordDecl *CanonicalRD = dyn_cast<RecordDecl>(RD->getCanonicalDecl());
  if (AvailableRecordDecls.count(CanonicalRD) || 
      TempAvailableRecordDecls.count(CanonicalRD))
    return;

  ForwardStr += RD->getKindName();
  ForwardStr += " ";
  ForwardStr += RD->getNameAsString() + ";\n";
  TempAvailableRecordDecls.insert(CanonicalRD);
}

void InstantiateTemplateParam::addForwardTemplateDeclStr(
       const ClassTemplateDecl *ClassTD,
       std::string &ForwardStr,
       RecordDeclSet &TempAvailableRecordDecls)
{
  const CXXRecordDecl *RD = ClassTD->getTemplatedDecl();
  const RecordDecl *CanonicalRD = dyn_cast<RecordDecl>(RD->getCanonicalDecl());
  if (AvailableRecordDecls.count(CanonicalRD) || 
      TempAvailableRecordDecls.count(CanonicalRD))
    return;

  std::string TemplateStr = "";
  RewriteHelper->getStringBetweenLocs(TemplateStr,
                                      ClassTD->getSourceRange().getBegin(),
                                      RD->getInnerLocStart());
  ForwardStr += TemplateStr;
  ForwardStr += RD->getKindName();
  ForwardStr += " ";
  ForwardStr += RD->getNameAsString() + ";\n";
  TempAvailableRecordDecls.insert(CanonicalRD);
}

void InstantiateTemplateParam::getForwardDeclStr(
       const Type *Ty,
       std::string &ForwardStr,
       RecordDeclSet &TempAvailableRecordDecls)
{
  if (const RecordType *RT = Ty->getAsUnionType()) {
#if LLVM_VERSION_MAJOR < 22
    const RecordDecl *RD = RT->getDecl();
#else
    const RecordDecl *RD = RT->getOriginalDecl();
#endif
    addOneForwardDeclStr(RD, ForwardStr, TempAvailableRecordDecls);
    return;
  }

  const CXXRecordDecl *CXXRD = Ty->getAsCXXRecordDecl();
  if (!CXXRD)
    return;

  const ClassTemplateSpecializationDecl *SpecD = 
    dyn_cast<ClassTemplateSpecializationDecl>(CXXRD);
  if (!SpecD) {
    addOneForwardDeclStr(CXXRD, ForwardStr, TempAvailableRecordDecls);
    return;
  }
  
  addForwardTemplateDeclStr(SpecD->getSpecializedTemplate(),
                            ForwardStr,
                            TempAvailableRecordDecls);

  const TemplateArgumentList &ArgList = SpecD->getTemplateArgs();
  unsigned NumArgs = ArgList.size();
  for (unsigned I = 0; I < NumArgs; ++I) {
    const TemplateArgument Arg = ArgList[I];
    if (Arg.getKind() != TemplateArgument::Type)
      continue;
    getForwardDeclStr(Arg.getAsType().getTypePtr(), 
                      ForwardStr,
                      TempAvailableRecordDecls);
  }
}

bool InstantiateTemplateParam::getTypeString(
       const QualType &QT, std::string &Str, std::string &ForwardStr)
{
  llvm::raw_string_ostream Strm(Str);
  QT.print(Strm, getPrintingPolicy(), ForwardStr);
  if (Str == "nullptr_t")
    Str = "decltype(nullptr)";

  FindForwardDeclVisitor(this, ForwardStr).TraverseType(QT);

  return true;
}

bool 
InstantiateTemplateParam::getTemplateArgumentString(const TemplateArgument &Arg,
                                                    std::string &ArgStr, 
                                                    std::string &ForwardStr)
{
  ArgStr = "";
  ForwardStr = "";
  if (Arg.getKind() != TemplateArgument::Type)
    return false;
  QualType QT = Arg.getAsType();
  return getTypeString(QT, ArgStr, ForwardStr);
}

void InstantiateTemplateParam::handleOneTemplateSpecialization(
       const TemplateDecl *D, const TemplateArgumentList & ArgList, const clang::Decl* Spec)
{
  if (isInIncludedFile(D))
    return;

  NamedDecl *TD = D->getTemplatedDecl();
  TemplateParameterSet ParamsSet;
  TemplateParameterVisitor ParameterVisitor(ParamsSet);
  ParameterVisitor.TraverseDecl(TD);

  unsigned NumArgs = ArgList.size(); (void)NumArgs;
  unsigned Idx = -1;
  TemplateParameterList *TPList = D->getTemplateParameters();
  for (NamedDecl* ND : *TPList) {
    ++Idx;
    // make it simple, skip NonTypeTemplateParmDecl and 
    // TemplateTemplateParmDecl for now
    const TemplateTypeParmDecl *TyParmDecl = 
      dyn_cast<TemplateTypeParmDecl>(ND);
    if (!TyParmDecl || TyParmDecl->isParameterPack())
      continue;
    // For classes we are not removing the template parameter right now
    // So we need to check that any replacement is performed
    if (isa<ClassTemplateDecl>(D) && !ParamsSet.count(ND))
      continue;

    TransAssert((Idx < NumArgs) && "Invalid Idx!");
    const TemplateArgument &Arg = ArgList.get(Idx);
    std::string ArgStr;
    std::string ForwardStr;
    if (!getTemplateArgumentString(Arg, ArgStr, ForwardStr))
      continue;
    // in case the argument has the same name as the parameter
    if (ArgStr == ND->getNameAsString())
      continue;
    ValidInstanceNum++;
    if (ValidInstanceNum == TransformationCounter) {
      TheInstantiationString = ArgStr;
      TheParameter = ND;
      TheParameterIdx = Idx;
      TheTemplateSpec = Spec;
      TheTemplateDecl = D;
      TheForwardDeclString = ForwardStr;
    }
  }
}
       
// TODO: handle partial specialization
void InstantiateTemplateParam::handleOneClassTemplateDecl(
       const ClassTemplateDecl *D)
{
  ClassTemplateDecl::spec_iterator I = D->spec_begin();
  ClassTemplateDecl::spec_iterator E = D->spec_end();
  if (I == E)
    return;
  ClassTemplateSpecializationDecl *SpecD = (*I);
  ++I;
  if (I != D->spec_end())
    return;
  handleOneTemplateSpecialization(D, SpecD->getTemplateArgs(), SpecD);
}

void InstantiateTemplateParam::handleOneFunctionTemplateDecl(
       const FunctionTemplateDecl *D)
{
  FunctionTemplateDecl::spec_iterator I = D->spec_begin();
  FunctionTemplateDecl::spec_iterator E = D->spec_end();
  if (I == E)
    return;
  const FunctionDecl *FD = (*I);
  ++I;
  if (I != D->spec_end())
    return;
  if (const FunctionTemplateSpecializationInfo *Info =
      FD->getTemplateSpecializationInfo()) {
    handleOneTemplateSpecialization(D, *(Info->TemplateArguments), FD);
  }
}

InstantiateTemplateParam::~InstantiateTemplateParam()
{
  delete CollectionVisitor;
  delete ParamRewriteVisitor;
}

