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
#include "llvm/Support/FormatVariadic.h"

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

HintsBuilder::HintScope HintsBuilder::MakeHintScope() {
  return HintScope(*this);
}

void HintsBuilder::ReverseOrder() { std::reverse(Hints.begin(), Hints.end()); }

std::string HintsBuilder::GetVocabularyJson() const {
  std::string Array;
  for (const auto &S : Vocab) {
    if (!Array.empty())
      Array += ",";
    Array += '"';
    // For simplicity, we assume no character needs escaping for JSON (always
    // true for replacement strings in clang_delta).
    Array += S;
    Array += '"';
  }
  return '[' + Array + ']';
}

std::vector<std::string> HintsBuilder::GetHintJsons() const {
  std::vector<std::string> Jsons;
  Jsons.reserve(Hints.size());
  for (const auto &H : Hints) {
    std::string Array;
    for (const auto &P : H.Patches) {
      if (!Array.empty())
        Array += ",";
      std::string Fields = llvm::formatv(R"txt("l":{0},"r":{1})txt", P.L, P.R);
      if (P.V.has_value())
        Fields += llvm::formatv(R"txt(,"v":{0})txt", *P.V);
      Array += '{';
      Array += std::move(Fields);
      Array += '}';
    }
    Jsons.push_back(llvm::formatv(R"txt({{"p":[{0}]})txt", Array));
  }
  return Jsons;
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
