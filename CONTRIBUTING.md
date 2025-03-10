# Welcome to the Substance 3D Designer DDS Exporter contributing guide <!-- omit in toc -->

In this guide you will get an overview of the contribution workflow from opening an issue, creating a pull request, reviewing, and merging the pull request.

## New contributor guide

To get an overview of the project, read the [README](README.md).
Here are some resources to help you get started with open source contributions:

- [Set up Git](https://docs.github.com/en/get-started/quickstart/set-up-git)
- [Collaborating with pull requests](https://docs.github.com/en/github/collaborating-with-pull-requests)
- Learn about [pre-commit hooks](https://pre-commit.com/)
- We use [ruff](https://docs.astral.sh/ruff/formatter/) formatting with a line-length of 120 characters.
- If you haven't yet setup an IDE, we recommend [Visual Studio Code](https://code.visualstudio.com/). See [Python in Visual Studio Code](https://code.visualstudio.com/docs/languages/python).

## Issues

### Create a new issue

If you spot a problem with the schemas or package, [search if an issue already exists](https://docs.github.com/en/github/searching-for-information-on-github/searching-on-github/searching-issues-and-pull-requests#search-by-the-title-body-or-comments).
If a related issue doesn't exist, you can open a new issue using a relevant [issue form](https://github.com/OlafHaag/substance-mipmaps-exporter/issues/new/choose).

### Solve an issue

Scan through our [existing issues](https://github.com/OlafHaag/substance-mipmaps-exporter/issues) to find one that interests you.
You can narrow down the search using `labels` as filters.

### Labels

Labels can help you find an issue you'd like to help with.
The [`good first issue` label](https://github.com/OlafHaag/substance-mipmaps-exporter/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22) is for problems or updates we think are ideal for new joiners.

## Contribute

### Get the Code

1. If you do not have maintainer access to the repository (you probably don't), [fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo).

2. [Clone](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) the (forked) repository to your local machine.

### Setting up Development Environment

It's best to use a separate Python _environment_ for development to avoid conflicts with other Python projects and keep your system Python clean. In this section we'll provide instructions on how to set up such an environment for the project.

We use [hatch](https://hatch.pypa.io/) as the Python package build backend and Python project manager.
We recommend to install it as it will provide you with a project-specific development environment, including the required Python version as a virtual environment. However, using hatch is not a necessity, but more of a convenience.  

1. You can read [hatch's installation instructions](https://hatch.pypa.io/latest/install/) for information on how to install it on your system.
You should get at least hatch **v1.10.0**.

2. Prepare the environment for development.
    Once you have setup hatch, navigate to the cloned repository, and execute:

    ```powershell
    hatch env create
    ```

    This will create a new virtual environment for development and install the development dependencies into it.
    An IDE like [Visual Studio Code](https://code.visualstudio.com/) can [detect hatch environments](https://hatch.pypa.io/latest/how-to/integrate/vscode/) for you to use it as the Python interpreter for this repository.
    It also installs [pre-commit](https://pre-commit.com/) hooks into the repository, which will run linting and formatting checks before you commit your changes.

    Alternatively, you can get the new environment path and add it to your IDE as a Python interpreter for this repository with:

    ```powershell
    hatch run python -c "import sys;print(sys.executable)"
    ```

    If you decided against using hatch, we still recommend installing the pre-commit hooks.

    ```powershell
    pre-commit install --overwrite -t pre-commit -t commit-msg -t pre-push
    ```

### Branch Off & Make Your Changes

1. Create a working branch and prefix its name with _fix/_ if it's a bug fix, or _feature/_ if it's a new feature.
    Start with your changes!  
    Have a look at the README for more information on how to use the package.

2. Write or update tests for your changes. <!-- TODO Explain how we do tests -->

3. Run tests with `hatch test --cover` and or run linting & formatting and tests with `hatch fmt` locally, as well as `hatch run types:check` for static type checking.

### Commit your update

Once you are happy with your changes, it's time to commit them.
Use [Conventional Commit messages](https://www.conventionalcommits.org/en/v1.0.0/).  
[Sign](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits) your commits!

If you followed the steps above, you should have a pre-commit hook installed that will automatically run the tests and linting before a commit succeeds.

Keep your individual commits small, so any breaking change can more easily be traced back to a commit.
A commit ideally only changes one single responsibility at a time.
If you keep the whole of your changes small and the branch short-lived, there's less risk to run into any other conflicts that can arise with the base.

Don't forget to [self-review](#self-review) to speed up the review process :zap:.

### Pull Request

When you're finished with the changes, create a __draft__ pull request, also known as a PR.

- Fill the "Ready for review" template so that we can review your PR. This template helps reviewers understand your changes as well as the purpose of your pull request.
- Don't forget to [link PR to issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/linking-a-pull-request-to-an-issue) if you are solving one.
- If you are not a maintainer of the plugin, enable the checkbox to [allow maintainer edits](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/allowing-changes-to-a-pull-request-branch-created-from-a-fork) so the branch can be updated for a merge.
Once you submit your PR, a maintainer will review your proposal. Give it some time, and be patient.
We may ask questions or request additional information.
- We may ask for changes to be made before a PR can be merged, either using [suggested changes](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/incorporating-feedback-in-your-pull-request) or pull request comments.
You can apply suggested changes directly through the UI.
You can make any other changes in your branch, and then commit them.
- As you update your PR and apply changes, mark each conversation as [resolved](https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/commenting-on-a-pull-request#resolving-conversations).
- If you run into any merge issues, checkout this [git tutorial](https://github.com/skills/resolve-merge-conflicts) to help you resolve merge conflicts and other issues.

### Self review

You should always review your own PR first.

Make sure that you:

- [ ] Confirm that the changes meet the user experience and goals outlined in the design plan (if there is one).
- [ ] Update the version of the schemas.
- [ ] Update the documentation if necessary.
- [ ] If there are any failing checks in your PR, troubleshoot them until they're all passing.

### Merging your PR

Once your PR has the required approvals, a maintainer will merge it.

We use a [squash & merge](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges#squash-and-merge-your-commits) by default to merge a PR.

The branch will be deleted automatically after the merge to prevent any more work being done the branch after it was merged.
