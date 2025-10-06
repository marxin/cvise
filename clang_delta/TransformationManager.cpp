//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2014, 2015, 2016, 2017, 2019, 2020 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#if HAVE_CONFIG_H
#  include <config.h>
#endif

#include "TransformationManager.h"

#include <iostream>
#include <sstream>

#include "clang/Basic/Builtins.h"
#include "clang/Basic/Diagnostic.h"
#include "clang/Basic/FileManager.h"
#include "clang/Basic/LangOptions.h"
#include "clang/Basic/LangStandard.h"
#include "clang/Basic/TargetInfo.h"
#include "clang/Lex/Preprocessor.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Parse/ParseAST.h"

#if LLVM_VERSION_MAJOR >= 20
#include "llvm/Support/VirtualFileSystem.h"
#endif

#include "Transformation.h"

using namespace std;
using namespace clang;

int TransformationManager::ErrorInvalidCounter = 1;

TransformationManager* TransformationManager::Instance;

std::map<std::string, Transformation *> *
TransformationManager::TransformationsMapPtr;

TransformationManager *TransformationManager::GetInstance()
{
  if (TransformationManager::Instance)
    return TransformationManager::Instance;

  TransformationManager::Instance = new TransformationManager();
  assert(TransformationManager::Instance);

  TransformationManager::Instance->TransformationsMap =
    *TransformationManager::TransformationsMapPtr;
  return TransformationManager::Instance;
}

Preprocessor &TransformationManager::getPreprocessor()
{
  return GetInstance()->ClangInstance->getPreprocessor();
}

bool TransformationManager::isCXXLangOpt()
{
  TransAssert(TransformationManager::Instance && "Invalid Instance!");
  TransAssert(TransformationManager::Instance->ClangInstance &&
              "Invalid ClangInstance!");
  return (TransformationManager::Instance->ClangInstance->getLangOpts()
          .CPlusPlus);
}

bool TransformationManager::isCLangOpt()
{
  TransAssert(TransformationManager::Instance && "Invalid Instance!");
  TransAssert(TransformationManager::Instance->ClangInstance &&
              "Invalid ClangInstance!");
  return (TransformationManager::Instance->ClangInstance->getLangOpts()
          .C99);
}

bool TransformationManager::isOpenCLLangOpt()
{
  TransAssert(TransformationManager::Instance && "Invalid Instance!");
  TransAssert(TransformationManager::Instance->ClangInstance &&
              "Invalid ClangInstance!");
  return (TransformationManager::Instance->ClangInstance->getLangOpts()
          .OpenCL);
}

bool TransformationManager::initializeCompilerInstance(std::string &ErrorMsg)
{
  if (ClangInstance) {
    ErrorMsg = "CompilerInstance has been initialized!";
    return false;
  }

  ClangInstance = new CompilerInstance();
  assert(ClangInstance);

#if LLVM_VERSION_MAJOR < 20
  ClangInstance->createDiagnostics();
#elif LLVM_VERSION_MAJOR < 22
  ClangInstance->createDiagnostics(*llvm::vfs::getRealFileSystem());
#else
  ClangInstance->createVirtualFileSystem(llvm::vfs::getRealFileSystem());
  ClangInstance->createDiagnostics();
#endif

  TargetOptions &TargetOpts = ClangInstance->getTargetOpts();
  if (const char *env = getenv("CVISE_TARGET_TRIPLE")) {
    TargetOpts.Triple = std::string(env);
  } else {
    TargetOpts.Triple = LLVM_DEFAULT_TARGET_TRIPLE;
  }
  llvm::Triple T(TargetOpts.Triple);
  CompilerInvocation &Invocation = ClangInstance->getInvocation();
  InputKind IK = FrontendOptions::getInputKindForExtension(
        StringRef(SrcFileName).rsplit('.').second);
  LangStandard::Kind LSTD = LangStandard::lang_unspecified;
  if (SetCXXStandard) {
    if (!CXXStandard.compare("c++98"))
      LSTD = LangStandard::Kind::lang_cxx98;
    else if (!CXXStandard.compare("c++11"))
      LSTD = LangStandard::Kind::lang_cxx11;
    else if (!CXXStandard.compare("c++14"))
      LSTD = LangStandard::Kind::lang_cxx14;
    else if (!CXXStandard.compare("c++17"))
      LSTD = LangStandard::Kind::lang_cxx17;
    else if (!CXXStandard.compare("c++20"))
      LSTD = LangStandard::Kind::lang_cxx20;

// TODO: simplify and use c++23 and c++26
#if LLVM_VERSION_MAJOR >= 17
    else if (!CXXStandard.compare("c++2b"))
      LSTD = LangStandard::Kind::lang_cxx23;
#else
    else if (!CXXStandard.compare("c++2b"))
      LSTD = LangStandard::Kind::lang_cxx2b;
#endif
    else {
      ErrorMsg = "Can't parse CXXStandard option argument!";
      return false;
    }
  }

  vector<string> includes;
  if (IK.getLanguage() == Language::C) {
    LangOptions::setLangDefaults(ClangInstance->getLangOpts(), Language::C, T, includes);
  }
  else if (IK.getLanguage() == Language::CXX) {
    // ISSUE: it might cause some problems when building AST
    // for a function which has a non-declared callee, e.g.,
    // It results an empty AST for the caller.
    LangOptions::setLangDefaults(ClangInstance->getLangOpts(), Language::CXX, T, includes, LSTD);
  }
  else if(IK.getLanguage() == Language::OpenCL) {
    //Commandline parameters
    std::vector<const char*> Args;
    Args.push_back("-x");
    Args.push_back("cl");
    Args.push_back("-Dcl_clang_storage_class_specifiers");

    const char *CLCPath = getenv("CVISE_LIBCLC_INCLUDE_PATH");

    ClangInstance->createFileManager();

    if(CLCPath != NULL && ClangInstance->hasFileManager() &&
#if LLVM_VERSION_MAJOR > 20
       ClangInstance->getFileManager().getDirectoryRef(CLCPath, false)
#else
       ClangInstance->getFileManager().getDirectory(CLCPath, false)
#endif
      ) {
        Args.push_back("-I");
        Args.push_back(CLCPath);
    }

    Args.push_back("-include");
    Args.push_back("clc/clc.h");
    Args.push_back("-fno-builtin");

    CompilerInvocation::CreateFromArgs(Invocation,
                                       Args,
                                       ClangInstance->getDiagnostics());
    LangOptions::setLangDefaults(ClangInstance->getLangOpts(),
                               Language::OpenCL,
			       T, includes);
  }
  else {
    ErrorMsg = "Unsupported file type!";
    return false;
  }

  TargetInfo *Target =
    TargetInfo::CreateTargetInfo(ClangInstance->getDiagnostics(),
#if LLVM_VERSION_MAJOR > 20
                                 ClangInstance->getInvocation().getTargetOpts()
#else
                                 ClangInstance->getInvocation().TargetOpts
#endif
                                );
  ClangInstance->setTarget(Target);

  if (const char *env = getenv("CVISE_INCLUDE_PATH")) {
    HeaderSearchOptions &HeaderSearchOpts = ClangInstance->getHeaderSearchOpts();

    const std::size_t npos = std::string::npos;
    std::string text = env;

    std::size_t now = 0, next = 0;
    do {
      next = text.find(':', now);
      std::size_t len = (next == npos) ? npos : (next - now);
      HeaderSearchOpts.AddPath(text.substr(now, len), clang::frontend::Angled, false, false);
      now = next + 1;
    } while(next != npos);
  }

  ClangInstance->createFileManager();
#if LLVM_VERSION_MAJOR < 22
  ClangInstance->createSourceManager(ClangInstance->getFileManager());
#else
  ClangInstance->createSourceManager();
#endif
  ClangInstance->createPreprocessor(TU_Complete);

  DiagnosticConsumer &DgClient = ClangInstance->getDiagnosticClient();
  DgClient.BeginSourceFile(ClangInstance->getLangOpts(),
                           &ClangInstance->getPreprocessor());
  ClangInstance->createASTContext();

  // It's not elegant to initialize these two here... Ideally, we
  // would put them in doTransformation, but we need these two
  // flags being set before Transformation::Initialize, which
  // is invoked through ClangInstance->setASTConsumer.
  if (DoReplacement)
    CurrentTransformationImpl->setReplacement(Replacement);
  if (DoPreserveRoutine)
    CurrentTransformationImpl->setPreserveRoutine(PreserveRoutine);
  if (CheckReference)
    CurrentTransformationImpl->setReferenceValue(ReferenceValue);

  assert(CurrentTransformationImpl && "Bad transformation instance!");
  ClangInstance->setASTConsumer(
    std::unique_ptr<ASTConsumer>(CurrentTransformationImpl));
  Preprocessor &PP = ClangInstance->getPreprocessor();
  PP.getBuiltinInfo().initializeBuiltins(PP.getIdentifierTable(),
                                         PP.getLangOpts());

  if (!ClangInstance->InitializeSourceManager(FrontendInputFile(SrcFileName, IK))) {
    ErrorMsg = "Cannot open source file!";
    return false;
  }

  return true;
}

void TransformationManager::Finalize()
{
  assert(TransformationManager::Instance);

  std::map<std::string, Transformation *>::iterator I, E;
  for (I = Instance->TransformationsMap.begin(),
       E = Instance->TransformationsMap.end();
       I != E; ++I) {
    // CurrentTransformationImpl will be freed by ClangInstance
    if ((*I).second != Instance->CurrentTransformationImpl)
      delete (*I).second;
  }
  delete Instance->TransformationsMapPtr;
  delete Instance->ClangInstance;
  delete Instance;
  Instance = NULL;
}

llvm::raw_ostream *TransformationManager::getOutStream()
{
  if (OutputFileName.empty())
    return &(llvm::outs());

  std::error_code EC;
  llvm::raw_fd_ostream *Out = new llvm::raw_fd_ostream(
      OutputFileName, EC, llvm::sys::fs::FA_Read | llvm::sys::fs::FA_Write);
  assert(!EC && "Cannot open output file!");
  return Out;
}

void TransformationManager::closeOutStream(llvm::raw_ostream *OutStream)
{
  if (!OutputFileName.empty())
    delete OutStream;
}

bool TransformationManager::doTransformation(std::string &ErrorMsg, int &ErrorCode)
{
  ErrorMsg = "";

  ClangInstance->createSema(TU_Complete, 0);
  DiagnosticsEngine &Diag = ClangInstance->getDiagnostics();
  Diag.setSuppressAllDiagnostics(true);
  Diag.setIgnoreAllWarnings(true);

  CurrentTransformationImpl->setWarnOnCounterOutOfBounds(WarnOnCounterOutOfBounds);
  CurrentTransformationImpl->setQueryInstanceFlag(QueryInstanceOnly);
  CurrentTransformationImpl->setTransformationCounter(TransformationCounter);
  CurrentTransformationImpl->setPreprocessor(&ClangInstance->getPreprocessor());
  if (ToCounter > 0) {
    if (CurrentTransformationImpl->isMultipleRewritesEnabled()) {
      CurrentTransformationImpl->setToCounter(ToCounter);
    }
    else {
      ErrorMsg = "current transformation[";
      ErrorMsg += CurrentTransName;
      ErrorMsg += "] does not support multiple rewrites!";
      return false;
    }
  }

  ParseAST(ClangInstance->getSema());

  ClangInstance->getDiagnosticClient().EndSourceFile();

  if (QueryInstanceOnly) {
    return true;
  }

  llvm::raw_ostream *OutStream = getOutStream();
  bool RV = true;
  if (CurrentTransformationImpl->transSuccess() && GenerateHints) {
    CurrentTransformationImpl->outputHints(*OutStream);
  }
  else if (CurrentTransformationImpl->transSuccess() && !GenerateHints) {
    CurrentTransformationImpl->outputTransformedSource(*OutStream);
  }
  else if (CurrentTransformationImpl->transInternalError() && !GenerateHints) {
    CurrentTransformationImpl->outputOriginalSource(*OutStream);
  }
  else {
    CurrentTransformationImpl->getTransErrorMsg(ErrorMsg);
    if (CurrentTransformationImpl->isInvalidCounterError())
      ErrorCode = ErrorInvalidCounter;
    RV = false;
  }
  closeOutStream(OutStream);
  return RV;
}

bool TransformationManager::verify(std::string &ErrorMsg, int &ErrorCode)
{
  if (!CurrentTransformationImpl) {
    ErrorMsg = "Empty transformation instance!";
    return false;
  }

  if (CurrentTransformationImpl->skipCounter())
    return true;

  if (TransformationCounter <= 0) {
    ErrorMsg = "Invalid transformation counter!";
    ErrorCode = ErrorInvalidCounter;
    return false;
  }

  if ((ToCounter > 0) && (ToCounter < TransformationCounter)) {
    ErrorMsg = "to-counter value cannot be smaller than counter value!";
    ErrorCode = ErrorInvalidCounter;
    return false;
  }

  return true;
}

void TransformationManager::registerTransformation(
       const char *TransName,
       Transformation *TransImpl)
{
  if (!TransformationManager::TransformationsMapPtr) {
    TransformationManager::TransformationsMapPtr =
      new std::map<std::string, Transformation *>();
  }

  assert((TransImpl != NULL) && "NULL Transformation!");
  assert((TransformationManager::TransformationsMapPtr->find(TransName) ==
          TransformationManager::TransformationsMapPtr->end()) &&
         "Duplicated transformation!");
  (*TransformationManager::TransformationsMapPtr)[TransName] = TransImpl;
}

void TransformationManager::printTransformations()
{
  llvm::outs() << "Registered Transformations:\n";

  std::map<std::string, Transformation *>::iterator I, E;
  for (I = TransformationsMap.begin(),
       E = TransformationsMap.end();
       I != E; ++I) {
    llvm::outs() << "  [" << (*I).first << "]: ";
    llvm::outs() << (*I).second->getDescription() << "\n";
  }
}

void TransformationManager::printTransformationNames()
{
  std::map<std::string, Transformation *>::iterator I, E;
  for (I = TransformationsMap.begin(),
       E = TransformationsMap.end();
       I != E; ++I) {
    llvm::outs() << (*I).first << "\n";
  }
}

void TransformationManager::outputNumTransformationInstances()
{
  int NumInstances =
    CurrentTransformationImpl->getNumTransformationInstances();
  llvm::outs() << "Available transformation instances: "
               << NumInstances << "\n";
}

void TransformationManager::outputNumTransformationInstancesToStderr()
{
  int NumInstances =
    CurrentTransformationImpl->getNumTransformationInstances();
  cerr  << "Available transformation instances: "
        << NumInstances << "\n";
}

TransformationManager::TransformationManager()
  : CurrentTransformationImpl(NULL),
    TransformationCounter(-1),
    ToCounter(-1),
    SrcFileName(""),
    OutputFileName(""),
    CurrentTransName(""),
    ClangInstance(NULL),
    GenerateHints(false),
    QueryInstanceOnly(false),
    DoReplacement(false),
    Replacement(""),
    DoPreserveRoutine(false),
    PreserveRoutine(""),
    CheckReference(false),
    ReferenceValue(""),
    SetCXXStandard(false),
    CXXStandard(""),
    WarnOnCounterOutOfBounds(false),
    ReportInstancesCount(false)
{
  // Nothing to do
}

TransformationManager::~TransformationManager()
{
  // Nothing to do
}

