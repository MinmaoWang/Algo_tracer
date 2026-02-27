
## 先export一个 api，例如在终端中运行：export DEEPSEEK_API_KEY=sk-xxxxxx

python cli.py \
--repo ../testrepo2 \
--target scikit-learn-main.sklearn.linear_model._base.LinearRegression.fit \
--hint-file scikit-learn-main/sklearn/linear_model/_base.py \
--outdir ../output_225/linear_LinearRegression_fit \
--max-iters 10 \
--explanation-prompt "深入解释这个函数的定义，对于一些你本身就理解的函数，或者对核心计算影响不大的函数，可以不用详细解释。"


python cli.py \
--repo ../testrepo2 \
--target scikit-learn-main.sklearn.linear_model._logistic.LogisticRegression \
--hint-file scikit-learn-main/sklearn/linear_model/_logistic.py \
--outdir ../output_224/linear_LogisticRegression \
--max-iters 10 \
--explanation-prompt "深入解释这个类的定义，需要对每一个子函数都去了解其定义，递归查找整个调用链以及逻辑。"


python cli.py \
--repo ../testrepo2 \
--target scikit-learn-main.sklearn.ensemble._gb.BaseGradientBoosting.fit \
--hint-file scikit-learn-main/sklearn/ensemble/_gb.py \
--outdir ../output_225/gb_BaseGradientBoosting_fit \
--max-iters 10 \
--explanation-prompt "简单介绍这个函数的定义以及调用逻辑"


python cli.py \
--repo ../test_repo \
--target main.main \
--hint-file main.py \
--outdir ../output_225/main_main \
--max-iters 10 \
--explanation-prompt "详细介绍这个代码的整体逻辑，解释完整的调用链，我需要知道每一个子函数的定义，需要在最后给我把函数的调用结构也描述出来"