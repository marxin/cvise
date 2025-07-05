#include "HintsBuilder.h"

#include <stdint.h>

#include <algorithm>
#include <string>
#include <utility>
#include <vector>

#include "clang/Basic/LangOptions.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Basic/SourceManager.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/FormatVariadic.h"

HintsBuilder::HintsBuilder(clang::SourceManager &SM,
                           const clang::LangOptions &LO)
    : SourceMgr(SM), NoOpRewriter(SourceMgr, LO) {}

HintsBuilder::~HintsBuilder() = default;

void HintsBuilder::AddPatch(clang::SourceRange R) {
  AddPatch(R.getBegin(), NoOpRewriter.getRangeSize(R));
}

void HintsBuilder::AddPatch(clang::CharSourceRange R) {
  AddPatch(R.getBegin(), NoOpRewriter.getRangeSize(R));
}

void HintsBuilder::AddPatch(clang::SourceLocation L, int64_t Len) {
  if (Len <= 0) {
    // This would be an invalid hint patch.
    return;
  }
  Patch P;
  P.L = SourceMgr.getFileOffset(L);
  P.R = P.L + Len;
  CurrentHint.Patches.push_back(P);
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

void HintsBuilder::ReverseOrder() { std::reverse(Hints.begin(), Hints.end()); }

std::vector<std::string> HintsBuilder::GetHintJsons() const {
  std::vector<std::string> Jsons;
  Jsons.reserve(Hints.size());
  for (const auto &H : Hints) {
    std::string Array;
    for (const auto &P : H.Patches) {
      if (!Array.empty())
        Array += ",";
      Array += llvm::formatv(R"txt({{"l":{0},"r":{1}})txt", P.L, P.R);
    }
    Jsons.push_back(llvm::formatv(R"txt({{"p":[{0}]})txt", Array));
  }
  return Jsons;
}
