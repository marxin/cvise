//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2014, 2015 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "MemberToGlobal.h"

#include "clang/AST/ASTContext.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Lex/Lexer.h"

#include "TransformationManager.h"

using namespace clang;

static const char* DescriptionMsg =
"Move declarations within a record (class or struct) in front of the record. \
The pass supports functions, variables, typedefs and nested records. \n";

static RegisterTransformation<MemberToGlobal>
         Trans("member-to-global", DescriptionMsg);

class MemberToGlobal::CollectionVisitor : public 
  RecursiveASTVisitor<CollectionVisitor> {

public:
  explicit CollectionVisitor(MemberToGlobal *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitRecordDecl(RecordDecl* RD) {
    for (auto* D : RD->decls())
      if (ConsumerInstance->isValidDecl(RD, D))
        ConsumerInstance->ValidDecls.push_back(std::make_pair(RD, D));

    return true;
  }

private:
  MemberToGlobal *ConsumerInstance;
};

class MemberToGlobal::RewriteVisitor : public RecursiveASTVisitor<RewriteVisitor> {

public:
  explicit RewriteVisitor(MemberToGlobal *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitMemberExpr(MemberExpr* ME) {
    if (!ME->isImplicitAccess() && ConsumerInstance->isTheDecl(ME->getMemberDecl())) {
      ConsumerInstance->TheRewriter.ReplaceText(ME->getOperatorLoc(), ",");
      ConsumerInstance->TheRewriter.InsertTextBefore(ME->getSourceRange().getBegin(), "(");
      ConsumerInstance->TheRewriter.InsertTextAfterToken(ME->getSourceRange().getEnd(), ")");
    }

    return true;
  }

  bool VisitElaboratedTypeLoc(ElaboratedTypeLoc TL) {
    // Replace CLASS::TYPE by TYPE
    if (auto* TT = TL.getInnerType()->getAs<TypedefType>()) {
      if (ConsumerInstance->isTheDecl(TT->getDecl())) {
        ConsumerInstance->removeRecordQualifier(TL.getQualifierLoc());
      }
    } else if (auto* TT = TL.getInnerType()->getAs<TagType>()) {
      if (ConsumerInstance->isTheDecl(TT->getDecl())) {
        ConsumerInstance->removeRecordQualifier(TL.getQualifierLoc());
      }
    }

    return true;
  }

  bool VisitDeclRefExpr(DeclRefExpr* DRE) {
    if (ConsumerInstance->isTheDecl(DRE->getDecl())) {
      ConsumerInstance->removeRecordQualifier(DRE->getQualifierLoc());
    }

    return true;
  }

private:
  MemberToGlobal *ConsumerInstance;
};

void MemberToGlobal::Initialize(ASTContext &context) 
{
  Transformation::Initialize(context);
}

StringRef MemberToGlobal::GetText(SourceRange replacementRange) {
  std::pair<FileID, unsigned> Begin = SrcManager->getDecomposedLoc(replacementRange.getBegin());
  std::pair<FileID, unsigned> End = SrcManager->getDecomposedLoc(replacementRange.getEnd());
  if (Begin.first != End.first)
    return "";

  StringRef MB = SrcManager->getBufferData(Begin.first);
  return MB.substr(Begin.second, End.second - Begin.second + 1);
}

void MemberToGlobal::removeRecordQualifier(const NestedNameSpecifierLoc& NNSLoc) {
  if (!NNSLoc)
    return;

  if (isTheRecordDecl(NNSLoc.getNestedNameSpecifier()->getAsRecordDecl())) {
    SourceRange SR = NNSLoc.getLocalSourceRange();
    SR.setEnd(SR.getEnd().getLocWithOffset(1));

    TheRewriter.RemoveText(SR);
  }
}

static bool replace(std::string& str, const std::string& from, const std::string& to) {
  size_t start_pos = str.find(from);
  if (start_pos == std::string::npos)
    return false;
  str.replace(start_pos, from.length(), to);
  return true;
}

void MemberToGlobal::HandleTranslationUnit(ASTContext &Ctx)
{
  CollectionVisitor(this).TraverseDecl(Ctx.getTranslationUnitDecl());

  ValidInstanceNum = ValidDecls.size();

  if (QueryInstanceOnly)
    return;

  if (TransformationCounter > ValidInstanceNum) {
    TransError = TransMaxInstanceError;
    return;
  }

  TheDecl = ValidDecls[TransformationCounter - 1].second;
  TheRecordDecl = ValidDecls[TransformationCounter - 1].first;
  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);

  auto RecordBegin = TheRecordDecl->getSourceRange().getBegin();
  auto BeginLoc = TheDecl->getSourceRange().getBegin();
  auto EndLoc = TheDecl->getSourceRange().getEnd();
  auto EndLoc2 = Lexer::getLocForEndOfToken(EndLoc, 0, *this->SrcManager, this->Context->getLangOpts());
  if (GetText(SourceRange(EndLoc2, EndLoc2)).str() == ";")
      EndLoc = EndLoc2;

  std::string Text = GetText(SourceRange(BeginLoc, EndLoc)).str();
  if (auto* VD = dyn_cast<VarDecl>(TheDecl)) {
    if (VD->isStaticDataMember()) {
      replace(Text, "static", "extern");
    }
  }

  TheRewriter.InsertTextBefore(RecordBegin, Text + "\n");
  TheRewriter.RemoveText(SourceRange(BeginLoc, EndLoc));

  for (auto* Redecl : TheDecl->redecls()) {
    if (auto* DD = dyn_cast<DeclaratorDecl>(Redecl)) {
      removeRecordQualifier(DD->getQualifierLoc());
    }
  }

  RewriteVisitor(this).TraverseDecl(Ctx.getTranslationUnitDecl());

  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

bool MemberToGlobal::isValidDecl(clang::RecordDecl* RD, clang::Decl* D) {
  if (D->isImplicit())
    return false;
  // No access specifier, e.g. public:
  if (isa<AccessSpecDecl>(D))
    return false;
  // No constructors or destructors
  if (isa<CXXConstructorDecl>(D) || isa<CXXDestructorDecl>(D))
    return false;
  // No friend declarations
  if (isa<FriendDecl>(D))
    return false;

  if (isInIncludedFile(D))
    return false;

  return true;
}
