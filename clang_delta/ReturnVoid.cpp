//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2014, 2015, 2019 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "ReturnVoid.h"

#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/ASTContext.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Lex/Lexer.h"
#include "clang/Lex/Preprocessor.h"

#include "TransformationManager.h"

using namespace clang;

static const char *DescriptionMsg =
"Make a function return void. \
Only change the prototype of the function and \
delete all return statements in the function, \
but skip the call sites of this function.\n";
 
static RegisterTransformation<ReturnVoid> 
         Trans("return-void", DescriptionMsg);

class RVASTVisitor : public RecursiveASTVisitor<RVASTVisitor> {
public:
  explicit RVASTVisitor(ReturnVoid *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitFunctionDecl(FunctionDecl *FD);

  bool VisitReturnStmt(ReturnStmt *RS);

private:

  ReturnVoid *ConsumerInstance;

  bool rewriteFuncDecl(FunctionDecl *FP);

  bool rewriteReturnStmt(ReturnStmt *RS);

};


class RVCollectionVisitor : public RecursiveASTVisitor<RVCollectionVisitor> {
public:
  explicit RVCollectionVisitor(ReturnVoid *Instance)
    : ConsumerInstance(Instance)
  { }

  bool VisitFunctionDecl(FunctionDecl *FD);

private:

  ReturnVoid *ConsumerInstance;
};

bool RVCollectionVisitor::VisitFunctionDecl(FunctionDecl *FD)
{
  if (ConsumerInstance->isInIncludedFile(FD))
    return true;

  FunctionDecl *CanonicalDecl = FD->getCanonicalDecl();
  if (ConsumerInstance->isNonVoidReturnFunction(CanonicalDecl)) {
    ConsumerInstance->ValidInstanceNum++;
    ConsumerInstance->ValidFuncDecls.push_back(CanonicalDecl);

    if (ConsumerInstance->ValidInstanceNum == 
        ConsumerInstance->TransformationCounter)
      ConsumerInstance->TheFuncDecl = CanonicalDecl;
  }

  if ((ConsumerInstance->TheFuncDecl == CanonicalDecl) && 
       FD->isThisDeclarationADefinition())
    ConsumerInstance->keepFuncDefRange(FD);

  return true;
}

void ReturnVoid::Initialize(ASTContext &context) 
{
  Transformation::Initialize(context);
  CollectionVisitor = new RVCollectionVisitor(this);
  TransformationASTVisitor = new RVASTVisitor(this);
}

bool ReturnVoid::isNonVoidReturnFunction(FunctionDecl *FD)
{
  // Avoid duplications
  if (std::find(ValidFuncDecls.begin(), 
                ValidFuncDecls.end(), FD) != 
      ValidFuncDecls.end())
    return false;

  // this function happen to have a library function, e.g. strcpy,
  // then the type source info won't be available, let's try to
  // get one from the one which is in the source
  if (!FD->getTypeSourceInfo()) {
    const FunctionDecl *FirstFD = FD->getCanonicalDecl();
    FD = NULL;
    for (FunctionDecl::redecl_iterator I = FirstFD->redecls_begin(), 
         E = FirstFD->redecls_end(); I != E; ++I) {
      if ((*I)->getTypeSourceInfo()) {
        FD = (*I);
        break;
      }
    }
    if (!FD)
      return false;
  }
  TypeLoc TLoc = FD->getTypeSourceInfo()->getTypeLoc();
  SourceLocation SLoc = TLoc.getBeginLoc();
  if (SLoc.isInvalid())
    return false;
  QualType RVType = FD->getReturnType();
  return !(RVType.getTypePtr()->isVoidType());
}

void ReturnVoid::keepFuncDefRange(FunctionDecl *FD)
{
  TransAssert(!FuncDefStartPos && !FuncDefEndPos && 
         "Duplicated function definition?");

  SourceRange FuncDefRange = FD->getSourceRange();

  SourceLocation StartLoc = FuncDefRange.getBegin();
  if (StartLoc.isMacroID()) {
    StartLoc = SrcManager->getExpansionLoc(StartLoc);
  }
  FuncDefStartPos = 
      SrcManager->getCharacterData(StartLoc);

  SourceLocation EndLoc = FuncDefRange.getEnd();
  FuncDefEndPos = 
      SrcManager->getCharacterData(EndLoc);
}

bool ReturnVoid::isInTheFuncDef(ReturnStmt *RS)
{
  // The candidate function doesn't have a body
  if (!FuncDefStartPos)
    return false;

  SourceRange RSRange = RS->getSourceRange();

  SourceLocation StartLoc = RSRange.getBegin();
  if (StartLoc.isMacroID()) {
    StartLoc = SrcManager->getExpansionLoc(StartLoc);
  }
  SourceLocation EndLoc = RSRange.getEnd();
  if (EndLoc.isMacroID()) {
    EndLoc = SrcManager->getExpansionLoc(EndLoc);
  }
  const char *StartPos =
      SrcManager->getCharacterData(StartLoc);
  const char *EndPos =   
      SrcManager->getCharacterData(EndLoc);
  (void)EndPos;

  if ((StartPos > FuncDefStartPos) && (StartPos < FuncDefEndPos)) {
    TransAssert((EndPos > FuncDefStartPos) && (EndPos < FuncDefEndPos) && 
            "Bad return statement range!");
    return true;
  }

  return false;
}

void ReturnVoid::HandleTranslationUnit(ASTContext &Ctx)
{
  CollectionVisitor->TraverseDecl(Ctx.getTranslationUnitDecl());

  if (QueryInstanceOnly)
    return;

  if (TransformationCounter > ValidInstanceNum) {
    TransError = TransMaxInstanceError;
    return;
  }

  TransAssert(TransformationASTVisitor && "NULL TransformationASTVisitor!");
  Ctx.getDiagnostics().setSuppressAllDiagnostics(false);
  TransAssert(TheFuncDecl && "NULL TheFuncDecl!");

  TransformationASTVisitor->TraverseDecl(Ctx.getTranslationUnitDecl());

  if (!Rewritten) {
    TransError = TransNoTextModificationError;
    return;
  }
  if (Ctx.getDiagnostics().hasErrorOccurred() ||
      Ctx.getDiagnostics().hasFatalErrorOccurred())
    TransError = TransInternalError;
}

// Copied from https://github.com/llvm/llvm-project/blob/main/clang-tools-extra/clang-tidy/modernize/UseTrailingReturnTypeCheck.cpp
struct ClassifiedToken {
  Token T;
  bool IsQualifier;
  bool IsSpecifier;
};

// Copied from https://github.com/llvm/llvm-project/blob/main/clang-tools-extra/clang-tidy/modernize/UseTrailingReturnTypeCheck.cpp
static bool hasAnyNestedLocalQualifiers(QualType Type) {
  bool Result = Type.hasLocalQualifiers();
  if (Type->isPointerType())
    Result = Result || hasAnyNestedLocalQualifiers(
      Type->castAs<PointerType>()->getPointeeType());
  if (Type->isReferenceType())
    Result = Result || hasAnyNestedLocalQualifiers(
      Type->castAs<ReferenceType>()->getPointeeType());
  return Result;
}

// Copied from https://github.com/llvm/llvm-project/blob/main/clang-tools-extra/clang-tidy/modernize/UseTrailingReturnTypeCheck.cpp
static SourceLocation expandIfMacroId(SourceLocation Loc,
  const SourceManager& SM) {
  if (Loc.isMacroID())
    Loc = expandIfMacroId(SM.getImmediateExpansionRange(Loc).getBegin(), SM);
  assert(!Loc.isMacroID() &&
    "SourceLocation must not be a macro ID after recursive expansion");
  return Loc;
}

// Copied from https://github.com/llvm/llvm-project/blob/main/clang-tools-extra/clang-tidy/modernize/UseTrailingReturnTypeCheck.cpp
static bool isCvr(Token T) {
  return T.isOneOf(tok::kw_const, tok::kw_volatile, tok::kw_restrict);
}

// Copied from https://github.com/llvm/llvm-project/blob/main/clang-tools-extra/clang-tidy/modernize/UseTrailingReturnTypeCheck.cpp
static bool isSpecifier(Token T) {
  return T.isOneOf(tok::kw_constexpr, tok::kw_inline, tok::kw_extern,
	tok::kw_static, tok::kw_friend, tok::kw_virtual);
}

// Copied from https://github.com/llvm/llvm-project/blob/main/clang-tools-extra/clang-tidy/modernize/UseTrailingReturnTypeCheck.cpp
static std::optional<ClassifiedToken>
classifyToken(const FunctionDecl& F, Preprocessor& PP, Token Tok) {
  ClassifiedToken CT;
  CT.T = Tok;
  CT.IsQualifier = true;
  CT.IsSpecifier = true;
  bool ContainsQualifiers = false;
  bool ContainsSpecifiers = false;
  bool ContainsSomethingElse = false;

  Token End;
  End.startToken();
  End.setKind(tok::eof);
  SmallVector<Token, 2> Stream{ Tok, End };

  // FIXME: do not report these token to Preprocessor.TokenWatcher.
  PP.EnterTokenStream(Stream, false, /*IsReinject=*/false);
  while (true) {
    Token T;
    PP.Lex(T);
    if (T.is(tok::eof))
      break;

    bool Qual = isCvr(T);
    bool Spec = isSpecifier(T);
    CT.IsQualifier &= Qual;
    CT.IsSpecifier &= Spec;
    ContainsQualifiers |= Qual;
    ContainsSpecifiers |= Spec;
    ContainsSomethingElse |= !Qual && !Spec;
  }

  // If the Token/Macro contains more than one type of tokens, we would need
  // to split the macro in order to move parts to the trailing return type.
  if (ContainsQualifiers + ContainsSpecifiers + ContainsSomethingElse > 1)
    return {};

  return CT;
}

// Copied from https://github.com/llvm/llvm-project/blob/main/clang-tools-extra/clang-tidy/modernize/UseTrailingReturnTypeCheck.cpp
std::optional<SmallVector<ClassifiedToken, 8>>
ReturnVoid::classifyTokensBeforeFunctionName(
  const FunctionDecl& F, const ASTContext& Ctx, const SourceManager& SM,
  const LangOptions& LangOpts) {
  SourceLocation BeginF = expandIfMacroId(F.getBeginLoc(), SM);
  SourceLocation BeginNameF = expandIfMacroId(F.getLocation(), SM);
  // Create tokens for everything before the name of the function.
  std::pair<FileID, unsigned> Loc = SM.getDecomposedLoc(BeginF);
  StringRef File = SM.getBufferData(Loc.first);
  const char* TokenBegin = File.data() + Loc.second;
  Lexer Lexer(SM.getLocForStartOfFile(Loc.first), LangOpts, File.begin(),
    TokenBegin, File.end());
  Token T;
  SmallVector<ClassifiedToken, 8> ClassifiedTokens;
  while (!Lexer.LexFromRawLexer(T) &&
    SM.isBeforeInTranslationUnit(T.getLocation(), BeginNameF)) {
    if (T.is(tok::raw_identifier)) {
      IdentifierInfo& Info = Ctx.Idents.get(
        StringRef(SM.getCharacterData(T.getLocation()), T.getLength()));
      if (Info.hasMacroDefinition()) {
        const MacroInfo* MI = PP->getMacroInfo(&Info);
        if (!MI || MI->isFunctionLike()) {
          // Cannot handle function style macros.
          //diag(F.getLocation(), Message);
          return {};
        }
      }
      T.setIdentifierInfo(&Info);
      T.setKind(Info.getTokenID());
    }
    if (std::optional<ClassifiedToken> CT = classifyToken(F, *PP, T))
      ClassifiedTokens.push_back(*CT);
    else {
      //diag(F.getLocation(), Message);
      return {};
    }
  }
  return ClassifiedTokens;
}

// Copied from https://github.com/llvm/llvm-project/blob/main/clang-tools-extra/clang-tidy/modernize/UseTrailingReturnTypeCheck.cpp
SourceRange ReturnVoid::findReturnTypeAndCVSourceRange(
  const FunctionDecl& F, const TypeLoc& ReturnLoc, const ASTContext& Ctx,
  const SourceManager& SM, const LangOptions& LangOpts) {
  // We start with the range of the return type and expand to neighboring
  // qualifiers (const, volatile and restrict).
  SourceRange ReturnTypeRange = F.getReturnTypeSourceRange();
  if (ReturnTypeRange.isInvalid()) {
    // Happens if e.g. clang cannot resolve all includes and the return type is
    // unknown.
    //diag(F.getLocation(), Message);
    return {};
  }
  // If the return type has no local qualifiers, it's source range is accurate.
  if (!hasAnyNestedLocalQualifiers(F.getReturnType()))
    return ReturnTypeRange;
  // Include qualifiers to the left and right of the return type.
  std::optional<SmallVector<ClassifiedToken, 8>> MaybeTokens =
    classifyTokensBeforeFunctionName(F, Ctx, SM, LangOpts);
  if (!MaybeTokens)
    return {};
  const SmallVector<ClassifiedToken, 8>& Tokens = *MaybeTokens;
  ReturnTypeRange.setBegin(expandIfMacroId(ReturnTypeRange.getBegin(), SM));
  ReturnTypeRange.setEnd(expandIfMacroId(ReturnTypeRange.getEnd(), SM));
  bool ExtendedLeft = false;
  for (size_t I = 0; I < Tokens.size(); I++) {
    // If we found the beginning of the return type, include left qualifiers.
    if (!SM.isBeforeInTranslationUnit(Tokens[I].T.getLocation(),
      ReturnTypeRange.getBegin()) &&
      !ExtendedLeft) {
      assert(I <= size_t(std::numeric_limits<int>::max()) &&
        "Integer overflow detected");
      for (int J = static_cast<int>(I) - 1; J >= 0 && Tokens[J].IsQualifier;
        J--)
        ReturnTypeRange.setBegin(Tokens[J].T.getLocation());
      ExtendedLeft = true;
    }
    // If we found the end of the return type, include right qualifiers.
    if (SM.isBeforeInTranslationUnit(ReturnTypeRange.getEnd(),
      Tokens[I].T.getLocation())) {
      for (size_t J = I; J < Tokens.size() && Tokens[J].IsQualifier; J++)
        ReturnTypeRange.setEnd(Tokens[J].T.getLocation());
      break;
    }
  }
  assert(!ReturnTypeRange.getBegin().isMacroID() &&
    "Return type source range begin must not be a macro");
  assert(!ReturnTypeRange.getEnd().isMacroID() &&
    "Return type source range end must not be a macro");
  return ReturnTypeRange;
}

bool RVASTVisitor::rewriteFuncDecl(FunctionDecl *FD)
{
  const TypeSourceInfo* TSI = FD->getTypeSourceInfo();
  if (TSI == nullptr)
    return true;

  // It is unbelievably difficult to determine the location of the return type including the const/volatile qualifiers
  SourceRange ReturnRange = ConsumerInstance->findReturnTypeAndCVSourceRange(*FD, TSI->getTypeLoc().IgnoreParens().getAs<FunctionTypeLoc>(), *ConsumerInstance->Context, *ConsumerInstance->SrcManager, ConsumerInstance->Context->getLangOpts());
  if (ReturnRange.isInvalid()) {
    ConsumerInstance->Rewritten = true;
    return !(ConsumerInstance->TheRewriter.InsertText(FD->getSourceRange().getBegin(), "void "));
  }

  SourceLocation BeginLoc = ReturnRange.getBegin();
  SourceLocation EndLoc = ReturnRange.getEnd();

  if (BeginLoc.isMacroID())
    BeginLoc = ConsumerInstance->SrcManager->getExpansionLoc(BeginLoc);
  if (EndLoc.isMacroID())
    EndLoc = ConsumerInstance->SrcManager->getExpansionLoc(EndLoc);

  if (!Rewriter::isRewritable(BeginLoc) || !Rewriter::isRewritable(EndLoc))
    return true;

  ConsumerInstance->Rewritten = true;
  return !(ConsumerInstance->TheRewriter.ReplaceText(SourceRange(BeginLoc, EndLoc), "void "));
}

bool RVASTVisitor::rewriteReturnStmt(ReturnStmt *RS)
{
  // SourceRange RSRange = RS->getSourceRange();

  // return !(ConsumerInstance->TheRewriter.ReplaceText(RSRange, "return"));

  // Instead of replace an entire ReturnStmt with return, let's keep Ret Expr.
  // The reason is that RetExpr could have side-effects and these side-effects
  // could cause bugs. But we still could remove "return" keyword

  ConsumerInstance->Rewritten = true;
  SourceLocation Loc = RS->getReturnLoc();
  return !(ConsumerInstance->TheRewriter.RemoveText(Loc, 6));
}

bool RVASTVisitor::VisitFunctionDecl(FunctionDecl *FD)
{
  FunctionDecl *CanonicalFD = FD->getCanonicalDecl();

  if (CanonicalFD == ConsumerInstance->TheFuncDecl)
    return rewriteFuncDecl(FD);

  return true;
}

bool RVASTVisitor::VisitReturnStmt(ReturnStmt *RS)
{
  if (ConsumerInstance->isInTheFuncDef(RS))
    return rewriteReturnStmt(RS);

  return true;
}

ReturnVoid::~ReturnVoid(void)
{
  delete CollectionVisitor;
  delete TransformationASTVisitor;
}

