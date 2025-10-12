#include "HintsBuilder.h"

#include <stdint.h>

#include <algorithm>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "clang/Basic/LangOptions.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Basic/SourceManager.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/raw_ostream.h"

HintsBuilder::HintScope::HintScope(HintsBuilder &B) : Builder(B) {}

HintsBuilder::HintScope::~HintScope() { Builder.FinishCurrentHint(); }

HintsBuilder::HintsBuilder(clang::SourceManager &SM,
                           const clang::LangOptions &LO)
    : SourceMgr(SM), NoOpRewriter(SourceMgr, LO) {}

HintsBuilder::~HintsBuilder() = default;

void HintsBuilder::AddPatch(clang::SourceRange R,
                            const std::string &Replacement) {
  AddPatch(R.getBegin(), NoOpRewriter.getRangeSize(R), Replacement);
}

void HintsBuilder::AddPatch(clang::CharSourceRange R,
                            const std::string &Replacement) {
  AddPatch(R.getBegin(), NoOpRewriter.getRangeSize(R), Replacement);
}

void HintsBuilder::AddPatch(clang::SourceLocation L, int64_t Len,
                            const std::string &Replacement) {
  if (Len <= 0) {
    // This would be an invalid hint patch.
    return;
  }
  Patch P;
  P.L = SourceMgr.getFileOffset(L);
  P.R = P.L + Len;
  if (!Replacement.empty())
    P.V = LookupOrCreateVocabId(Replacement);
  CurrentHint.Patches.push_back(P);
}

void HintsBuilder::AddPatch(clang::SourceLocation L, const std::string &Insertion) {
  if (Insertion.empty()) {
    // Empty insertion is a no-op.
    return;
  }
  Patch P;
  P.L = SourceMgr.getFileOffset(L);
  P.R = P.L;
  P.V = LookupOrCreateVocabId(Insertion);
  CurrentHint.Patches.push_back(P);
}

HintsBuilder::HintScope HintsBuilder::MakeHintScope() {
  return HintScope(*this);
}

void HintsBuilder::ReverseOrder() { std::reverse(Hints.begin(), Hints.end()); }

void HintsBuilder::Output(llvm::raw_ostream &OutStream) const {
  OutStream << Vocab.size() << '\n';
  // Separate vocabulary strings with the null character, to avoid the
  // complexity of escaping JSON strings here.
  for (const auto &S : Vocab)
    OutStream << S << '\0';
  for (const auto &H : Hints) {
    OutStream << "{\"p\":[";
    bool First = true;
    for (const auto &P : H.Patches) {
      if (!First)
        OutStream << ',';
      First = false;
      OutStream << '{';
      OutStream << "\"l\":" << P.L << ",\"r\":" << P.R;
      if (P.V.has_value())
        OutStream << ",\"v\":" << *P.V;
      OutStream << '}';
    }
    OutStream << "]}\n";
  }
}

void HintsBuilder::FinishCurrentHint() {
  if (CurrentHint.Patches.empty()) {
    // This shouldn't happen normally, but because it's hard to guarantee and
    // because an empty hint would trigger errors in C-Vise we add this
    // safeguard here.
    return;
  }
  Hints.push_back(std::move(CurrentHint));
  CurrentHint = {};
}

int64_t HintsBuilder::LookupOrCreateVocabId(const std::string &S) {
  // This implementation adds up to being quadratic of the size of vocabulary,
  // but we assume the number of unique replacement strings in clang_delta to be
  // small.
  auto It = std::find(Vocab.begin(), Vocab.end(), S);
  if (It != Vocab.end())
    return static_cast<int64_t>(It - Vocab.begin());
  Vocab.push_back(S);
  return static_cast<int64_t>(Vocab.size() - 1);
}
