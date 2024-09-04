FROM ubuntu:rolling
RUN apt-get update
RUN apt-get -qq install -y gcc g++ wget lsb-release wget software-properties-common gnupg git cmake flex python3-pebble python3-psutil python3-chardet python3-pytest vim unifdef
RUN wget https://apt.llvm.org/llvm.sh
RUN chmod +x llvm.sh
RUN ./llvm.sh 20
RUN apt-get install -y bolt-20 clang-20 libclang-common-20-dev libclang-20-dev mlir-20-tools llvm-20-tools libclang-common-20-dev libclang-20-dev libclang1-20 clang-format-20 python3-clang-20 clangd-20 clang-tidy-20 libomp-20-dev
RUN touch /usr/lib/llvm-20/lib/libLibcTableGenUtil.a
RUN ln -s /usr/lib/x86_64-linux-gnu/libclang-cpp.so.20.0 /usr/lib/llvm-20/lib/libclang-cpp.so.20.0
RUN mkdir -p /tmp/cvise/build-docker
WORKDIR /tmp/cvise/build-docker
