# GHstats

A probably over-engineered project to show some statistics using data pulled from the
GitHub API :)

[Here's my instance!](https://ichard26.github.io/ghstats/)

## Features

- Simple setup
- Automated front-end generation
- Automatic management of GitHub data and view data (initial downloading and
  updating are handled for you!)

GHstats supports these "views" at the moment:

1. `issue-counts`
1. `pull-counts`
1. `issue-deltas`
1. `issue-closers`

## Setting up your own instance

### Configuring GHstats & generating HTML

1. Clone this repository with only the `main` branch

   ```bash
   git clone https://github.com/ichard26/ghstats.git --single-branch
   ```

1. Run `nox -s run-ghstats -R -- setup` and follow/answer the prompts

   ```console
   $ nox -s run-ghstats -R -- setup
   nox > Running session run-ghstats
   nox > Creating virtual environment (virtualenv) using python in .nox/run-ghstats
   nox > python -m pip install attrs click colorama jinja2
   nox > python -m scripts.ghstats setup
   [ghstats] Deleted web directory.
   Instance title: Richard's GHstats instance
   Instance repository name (used to set up relative URLs): ghstats
   GitHub username (used in user-agent + footer): ichard26
   [ghstats] Configuration saved!
   Would you like to add a repository to your instance? [Y/n]: y
   Repository ($owner/$name): psf/black
   Add 'issue-counts' (open issues over time) view? [Y/n]: y
   Add 'pull-counts' (open pull requests over time) view? [Y/n]: y
   Add 'issue-deltas' (monthly delta of open issues over time) view? [Y/n]: y
   Add 'issue-closers' (number of issues closed by collaborators over time) view? [Y/n]: y
   [ghstats] Added 'psf/black' to configuration.
   [ghstats] Wrote index page.
   [ghstats] Wrote HTML for 'psf/black'.
   [ghstats] Wrote Vite build configuration.
   [ghstats] Copied static assets. Web directory is ready!
   nox > Session run-ghstats was successful.
   ```

1. If you'd like to track stats for another repository, you can run
   `nox -s run-ghstats -- add-repository`

   You can repeat this step to add as many repositories as you want (although if you add
   too many repositories at once, the `Refresh assets` GHA workflow may run API rate
   limits).

1. Stage and commit the new/updated files and directories: `config.json`and `web/`

### Deployment

1. Create a new repository on GitHub and push your local Git repository to it (manually
   or using `gh`)
1. Either locally or via the GitHub web interface, create a new branch called `production`
1. Go into your repository settings under the `Pages` tab and ...
   - Set `Source` to `Deploy from a branch`
   - Set `Branch` to `production`
1. Trigger a new run of the `Refresh assets` GHA workflow from the `Actions` tab
1. Observe `production` being updated and your new instance being deployed to GitHub
   Pages ...

If the website is up and looks good, congrats! You've set up your own instance. It
shouldn't require any maintenance on your part from now on. The workflow will
automatically run every day and push updates as needed.

**Note**: the `Refresh assets` workflow will probably fail after step one since the
`production` branch doesn't exist yet, just ignore the first failure.
