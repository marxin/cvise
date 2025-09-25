// Prints information about each text inclusion directive (like "#include").
//
// Input should be the full compiler command line, e.g.:
//   clang_include_graph clang -Dfoo bar.c
//
// Output is a list of quadruples: the source file path, the begin and end
// locations (as byte indices in the source file), the included file path. The
// items are separated with a null character.

#include <limits>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include "clang/Basic/Diagnostic.h"
#include "clang/Basic/DiagnosticIDs.h"
#include "clang/Basic/DiagnosticOptions.h"
#include "clang/Basic/FileEntry.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/CompilerInvocation.h"
#include "clang/Frontend/FrontendAction.h"
#include "clang/Frontend/FrontendActions.h"
#include "clang/Frontend/FrontendOptions.h"
#include "clang/Lex/PPCallbacks.h"
#include "clang/Lex/Preprocessor.h"
#include "clang/Lex/Token.h"
#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Execution.h"
#include "llvm/ADT/IntrusiveRefCntPtr.h"
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
    outs() << SourceMgr.getFilename(HashLoc) << '\0' << L << '\0' << R << '\0'
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

// Suppresses errors, to make command-line arg parsing succeed even if unknown
// arguments are passed.
class SuppressingDiagConsumer : public DiagnosticConsumer {
  bool IncludeInDiagnosticCounts() const override { return false; }
  void HandleDiagnostic(DiagnosticsEngine::Level DiagLevel,
                        const Diagnostic &Info) override {}
};

} // namespace

static cl::extrahelp CommonHelp(CommonOptionsParser::HelpMessage);
static cl::OptionCategory ToolCategory("clang_include_graph options");

static std::vector<std::string> getSourcePaths(int argc, const char **argv) {
  std::vector<const char *> Args(argv + 1, argv + argc);
  llvm::IntrusiveRefCntPtr<clang::DiagnosticOptions> DiagOpts =
      new clang::DiagnosticOptions();
  SuppressingDiagConsumer DiagConsumer;
  llvm::IntrusiveRefCntPtr<clang::DiagnosticsEngine> Diags =
      new clang::DiagnosticsEngine(
          llvm::IntrusiveRefCntPtr<clang::DiagnosticIDs>(
              new clang::DiagnosticIDs()),
#if LLVM_VERSION_MAJOR < 21
          &*DiagOpts,
#else
          &*DiagOpts,
#endif
          &DiagConsumer, /*ShouldOwnClient=*/false);

  auto Invocation = std::make_shared<clang::CompilerInvocation>();
  if (!clang::CompilerInvocation::CreateFromArgs(*Invocation, Args, *Diags)) {
    llvm::errs() << "Failed to create CompilerInvocation from args\n";
    exit(1);
  }

  const clang::FrontendOptions &FEOpts = Invocation->getFrontendOpts();
  std::vector<std::string> SourcePaths;
  for (const auto &Input : FEOpts.Inputs) {
    if (Input.isFile() && Input.getKind().getFormat() == InputKind::Source)
      SourcePaths.emplace_back(Input.getFile());
  }
  return SourcePaths;
}

int main(int argc, const char **argv) {
  llvm::sys::PrintStackTraceOnErrorSignal(argv[0]);

  std::vector<std::string> SourcePaths = getSourcePaths(argc - 1, argv + 1);
  if (SourcePaths.empty()) {
    errs() << "No source files found in the command line\n";
    return 0;
  }

  std::vector<const char *> SynthesizedCmd;
  SynthesizedCmd.push_back(argv[1]);
  for (const auto &SP : SourcePaths)
    SynthesizedCmd.push_back(SP.c_str());
  SynthesizedCmd.push_back("--");
  SynthesizedCmd.insert(SynthesizedCmd.end(), argv + 2, argv + argc);
  int Size = SynthesizedCmd.size();

  auto Executor = createExecutorFromCommandLineArgs(Size, SynthesizedCmd.data(),
                                                    ToolCategory);
  if (!Executor) {
    errs() << toString(Executor.takeError()) << "\n";
    return 1;
  }

  auto Err =
      Executor->get()->execute(std::make_unique<InclusionGraphActionFactory>());
  if (Err)
    errs() << toString(std::move(Err)) << "\n";
}
