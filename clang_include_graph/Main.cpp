#include <limits>
#include <memory>
#include <utility>

#include "clang/Basic/FileEntry.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendAction.h"
#include "clang/Frontend/FrontendActions.h"
#include "clang/Lex/PPCallbacks.h"
#include "clang/Lex/Preprocessor.h"
#include "clang/Lex/Token.h"
#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Execution.h"
#include "llvm/ADT/StringExtras.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/Signals.h"
#include "llvm/Support/raw_ostream.h"

using namespace clang;
using namespace clang::tooling;
using namespace llvm;

namespace {

// Observes every inclusion directive (#include et al.) and prints information
// about it.
class InclusionGraphPPCallback : public PPCallbacks {
public:
  explicit InclusionGraphPPCallback(const SourceManager &SourceMgr)
      : SourceMgr(SourceMgr) {}

  void InclusionDirective(SourceLocation HashLoc, const Token &IncludeTok,
                          StringRef FileName, bool IsAngled,
                          CharSourceRange FilenameRange,
                          OptionalFileEntryRef File, StringRef SearchPath,
                          StringRef RelativePath,
#if LLVM_VERSION_MAJOR < 19
                          const clang::Module *Imported,
#else
                          const Module *SuggestedModule, bool ModuleImported,
#endif
                          SrcMgr::CharacteristicKind FileType) override {
    if (!File) {
      // Ignore broken includes.
      return;
    }
    SourceLocation EndOfLine = SourceMgr.translateLineCol(
        SourceMgr.getFileID(HashLoc), SourceMgr.getSpellingLineNumber(HashLoc),
        /*Col=*/std::numeric_limits<unsigned>::max());
    unsigned L = SourceMgr.getFileOffset(HashLoc);
    unsigned R = SourceMgr.getFileOffset(EndOfLine);
    outs() << SourceMgr.getFilename(HashLoc) << '\0'
           << L << '\0'
           << R << '\0'
           << File->getName() << '\0';
  }

private:
  const SourceManager &SourceMgr;
};

// Frontend action that instantiates and enables `InclusionGraphPPCallback`.
class InclusionGraphAction : public PreprocessOnlyAction {
public:
  bool BeginSourceFileAction(CompilerInstance &CI) override {
    CI.getPreprocessor().addPPCallbacks(
        std::make_unique<InclusionGraphPPCallback>(CI.getSourceManager()));
    return true;
  }
};

// Factory for `InclusionGraphAction`, which builds the inclusion graph.
class InclusionGraphActionFactory : public FrontendActionFactory {
public:
  std::unique_ptr<FrontendAction> create() override {
    return std::make_unique<InclusionGraphAction>();
  }
};

} // namespace

static cl::extrahelp CommonHelp(CommonOptionsParser::HelpMessage);
static cl::OptionCategory ToolCategory("clang_include_graph options");

int main(int argc, const char **argv) {
  llvm::sys::PrintStackTraceOnErrorSignal(argv[0]);

  auto Executor = createExecutorFromCommandLineArgs(argc, argv, ToolCategory);
  if (!Executor) {
    errs() << toString(Executor.takeError()) << "\n";
    return 1;
  }

  auto Err =
      Executor->get()->execute(std::make_unique<InclusionGraphActionFactory>());
  if (Err) {
    errs() << toString(std::move(Err)) << "\n";
  }
}
