# Лицензии и происхождение

Собственный код — Apache-2.0, полный текст LICENSE. Данные конкурса, разметка, аннотации и outputs не входят в лицензию кода. Code-only Git не включает установленные зависимости, runtimes или веса.

| Компонент | Код | Веса | Источник |
|---|---|---|---|
| Microsoft XCLIP | MIT upstream; Apache-2.0 native Transformers | MIT | [Официальная model card](https://huggingface.co/microsoft/xclip-base-patch32), [VideoX LICENSE](https://github.com/microsoft/VideoX/blob/master/LICENSE). Точная ревизия/SHA256 и пределы проверки — [XCLIP-PROTO-01](xclip-candidate.md). |
| InternVL3.5-1B-HF | Apache-2.0 native Transformers, без remote code | Apache-2.0 | [Официальная model card](https://huggingface.co/OpenGVLab/InternVL3_5-1B-HF), [проверенные пины и контроль](internvl-visual-control.md). Модель отклонена по synthetic gate; это не принятый detector. |
| Qwen3-VL-2B-Instruct | Apache-2.0 | Apache-2.0 | [Официальная model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct), [код Qwen](https://github.com/QwenLM/Qwen3-VL). Пин ревизии и SHA256 сохраняются после завершения в models/provenance.json. |
| DINOv2-small, эксперимент | Apache-2.0 | Apache-2.0 | [Официальная model card](https://huggingface.co/facebook/dinov2-small), [LICENSE](https://github.com/facebookresearch/dinov2/blob/main/LICENSE), проверенный SHA256 в models/dinov2-small/provenance.json. |
| Transformers | Apache-2.0 | отдельно | [Официальный LICENSE](https://github.com/huggingface/transformers/blob/main/LICENSE), metadata установленного пакета. |
| LM Format Enforcer | MIT | нет | [Официальный репозиторий](https://github.com/noamgat/lm-format-enforcer), версия 0.11.3, текст лицензии docs/lmfe-license.txt. Небольшой адаптер tokenizer-data API сохраняет attribution Noam Gat; upstream интеграция опубликованного wheel несовместима с Transformers 5. |
| llama.cpp b11712 | MIT | отдельно | [Официальный LICENSE](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE). Фактически исследованный portable CUDA 12.4 runtime; ветка не прошла semantic gates. Пины в config/gguf-artifacts.json. |
| Qwen3-VL-4B-Instruct-GGUF | runtime MIT | Apache-2.0 | [Официальный репозиторий Qwen](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF). Исследованная ветка, не принятый detector; revision 1cd86afb9a95c410a6038ab3b40d8b578c892266, Q4_K_M и F16 mmproj закреплены в config/gguf-artifacts.json. |
| cloudflared 2026.10.1 | Apache-2.0 | нет | [Upstream LICENSE](https://github.com/cloudflare/cloudflared/blob/master/LICENSE). Portable connector используется для ограниченного по сроку HTTPS-доступа к локальному прототипу и отдельных synthetic-only HTTPS/rollback проверок; AI inference выполняется локально. Бинарник исключён из Git. Пин в config/cloudflared-artifact.json. |

Лицензии указанных моделей разрешают коммерческое использование при соблюдении условий. При распространении сохранять copyright, LICENSE и upstream NOTICE, когда он имеется. Проверка кода не заменяет проверку весов.

Metadata окружения сохранены в .private/licenses/package-metadata.json: FastAPI MIT, Starlette BSD-3-Clause, python-multipart Apache-2.0, PyAV BSD-3-Clause, Pillow MIT-CMU. PyTorch включает несколько лицензий BSD/MIT/Apache/BSL; полные тексты поставляет upstream. CUDA-runtime и драйверы имеют отдельные условия NVIDIA и не включаются в code-only Git.

Лицензия PyAV не покрывает автоматически все нативные DLL. Установленные avcodec/avformat/avutil сообщают `LGPL version 3 or later`; фактические configuration и вызовы `*_license()` сохранены в .private/licenses/ffmpeg.json. Сборка включает libx264/libx265. Весь wheel не объявляется permissive-only. Для бинарной поставки банку нужна отдельная проверка notices, соответствующих исходников и возможности замены библиотек по условиям точной сборки и кодеков. Сейчас зависимости не перепаковываются. См. [FFmpeg Legal](https://ffmpeg.org/legal.html) и [LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.html).

Microsoft Edge используется только для синтетического QA и не входит в продукт. Python dependency audit не проверяет нативные кодеки и лицензии.
