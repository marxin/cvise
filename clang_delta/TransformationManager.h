//===----------------------------------------------------------------------===//
//
// Copyright (c) 2012, 2013, 2015, 2016 The University of Utah
// All rights reserved.
//
// This file is distributed under the University of Illinois Open Source
// License.  See the file COPYING for details.
//
//===----------------------------------------------------------------------===//

#ifndef TRANSFORMATION_MANAGER_H
#define TRANSFORMATION_MANAGER_H

#include <string>
#include <map>
#include <cassert>

#include "llvm/Support/raw_ostream.h"

class Transformation;
namespace clang {
  class CompilerInstance;
  class Preprocessor;
}

class TransformationManager {

public:

  static TransformationManager *GetInstance();

  static void Finalize();

  static void registerTransformation(const char *TransName, 
                                     Transformation *TransImpl);
  
  static bool isCXXLangOpt();

  static bool isCLangOpt();

  static bool isOpenCLLangOpt();

  static clang::Preprocessor &getPreprocessor();

  static int ErrorInvalidCounter;

  bool doTransformation(std::string &ErrorMsg, int &ErrorCode);

  bool verify(std::string &ErrorMsg, int &ErrorCode);

  int setTransformation(const std::string &Trans) {
    if (TransformationsMap.find(Trans.c_str()) == TransformationsMap.end())
      return -1;
    CurrentTransName = Trans;
    CurrentTransformationImpl = TransformationsMap[Trans.c_str()];
    return 0;
  }

  void setTransformationCounter(int Counter) {
    assert((Counter > 0) && "Bad Counter value!");
    TransformationCounter = Counter;
  }

  void setToCounter(int Counter) {
    assert((Counter > 0) && "Bad to-counter value!");
    ToCounter = Counter;
  }

  void setSrcFileName(const std::string &FileName) {
    assert(SrcFileName.empty() && "Could only process one file each time");
    SrcFileName = FileName;
  }

  void setOutputFileName(const std::string &FileName) {
    OutputFileName = FileName;
  }

  void setReplacement(const std::string &Str) {
    Replacement = Str;
    DoReplacement = true;
  }

  void setPreserveRoutine(const std::string &Str) {
    PreserveRoutine = Str;
    DoPreserveRoutine = true;
  }

  void setReferenceValue(const std::string &Str) {
    ReferenceValue = Str;
    CheckReference = true;
  }

  void setQueryInstanceFlag(bool Flag) {
    QueryInstanceOnly = Flag;
  }

  bool getQueryInstanceFlag() {
    return QueryInstanceOnly;
  }

  void setCXXStandard(const std::string &Str) {
    CXXStandard = Str;
    SetCXXStandard = true;
  }

  void setReportInstancesCount(bool Flag) {
    ReportInstancesCount = Flag;
  }

  bool getReportInstancesCount() {
    return ReportInstancesCount;
  }

  void setWarnOnCounterOutOfBounds(bool Flag) {
    WarnOnCounterOutOfBounds = Flag;
  }

  bool initializeCompilerInstance(std::string &ErrorMsg);

  void outputNumTransformationInstances();

  void outputNumTransformationInstancesToStderr();

  void printTransformations();

  void printTransformationNames();

private:
  
  TransformationManager();

  ~TransformationManager();

  llvm::raw_ostream *getOutStream();

  void closeOutStream(llvm::raw_ostream *OutStream);

  static TransformationManager *Instance;

  static std::map<std::string, Transformation *> *TransformationsMapPtr;

  std::map<std::string, Transformation *> TransformationsMap;

  Transformation *CurrentTransformationImpl;

  int TransformationCounter;

  int ToCounter;

  std::string SrcFileName;

  std::string OutputFileName;

  std::string CurrentTransName;

  clang::CompilerInstance *ClangInstance;

  bool QueryInstanceOnly;

  bool DoReplacement;

  std::string Replacement;

  bool DoPreserveRoutine;

  std::string PreserveRoutine;

  bool CheckReference;

  std::string ReferenceValue;

  bool SetCXXStandard;

  std::string CXXStandard;

  bool WarnOnCounterOutOfBounds;

  bool ReportInstancesCount;

  // Unimplemented
  TransformationManager(const TransformationManager &);

  void operator=(const TransformationManager&);

};

template<typename TransformationClass, typename... Args>
class RegisterTransformation {

public:
  RegisterTransformation(const char *TransName, const char *Desc, Args... args) {
    Transformation *TransImpl = new TransformationClass(TransName, Desc, args...);
    assert(TransImpl && "Fail to create TransformationClass");
 
    TransformationManager::registerTransformation(TransName, TransImpl);
  }

private:
  // Unimplemented
  RegisterTransformation(const RegisterTransformation &);

  void operator=(const RegisterTransformation &);

};

#endif
