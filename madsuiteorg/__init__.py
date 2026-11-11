import datetime
import os
import pybtex
import setuptools
import yaml
import shutil
import importlib.resources as pkg_resources
import subprocess
from livereload import Server, shell
from pybtex.database import parse_file
from pybtex.plugin import find_plugin
from livereload import Server

# Constants
BUILD_DIR = '_build'

def generate_html(output, content, template, title, year, links): 
    """Generates an HTML file by replacing placeholders in the TEMPLATE."""        
    html_content = template.format(title=title, content=content, year=year)
    for link in links:
        
        html_content = html_content.replace(
            f"{{{link['name']}}}",
            f"""
            <a href="{link['url']}">{link['name']}</a>
            """
        )

    with open(output, 'w', encoding='utf-8') as file:
        file.write(html_content)
    print(f"Generated {output} successfully.")

def build():
    YEAR = datetime.datetime.now().year
    DATA = yaml.safe_load(open(
        pkg_resources.files(__package__).joinpath('data/data.yaml'),
        'r',
        encoding='utf-8'))
    TITLE = DATA.get('title', 'MadSuite')
    INTRO = DATA.get('intro', '')
    DESCRIPTION = DATA.get('description', '')
    MEMBERS = DATA.get('members', [])
    PACKAGES = DATA.get('packages', [])
    NEWS = DATA.get('news', [])
    LINKS = DATA.get('links', [])
    DOMAIN = DATA.get('domain', '')
    
    TEMPLATE = open(
        pkg_resources.files(__package__).joinpath('data/template.html'),
        'r', encoding='utf-8').read()

    """Main function to generate the HTML content and create the index.html file."""
    # Generate HTML list for packages
    members_html = "\n".join([
        f"""
        <li>
            <a href="{member['url']}"><strong>{member['name']}</strong></a> (<a href="https://github.com/{member['github']}">@{member['github']}</a>): {member['description']}
        </li>
        """ for member in MEMBERS
    ])
    
    news_html = "\n".join([
        f"""
        <li>
        {news['entry']} (<a href="{news['link']}">{news['date']}</a>)
        </li>
        """ for news in NEWS
    ])

    resources_html = "\n".join([
        f"""
        <li>
        {resource['description']} [ <a href="{resource['url']}">Link</a> ]
        </li>
        """ for resource in DATA.get('resources', [])
    ])

    packages_html = "\n".join([
        f"""
        <h4 class="mt-4">{cat['category']}</h4>
        <ul>
        """ + "\n".join([
            f"""
            <li>
                <strong><a href="{pkg['url']}">{pkg['name']}</a></strong>: {pkg['description']}
            </li>
            """ for pkg in cat['items']
        ]) + "</ul>"
        for cat in PACKAGES
    ])

    talks_html = "\n".join([
        f"""
        <li>
        <strong>{talk['title']}</strong> ({talk['date']}){(', ' + talk['speaker']) if talk.get('speaker') else ''}: {talk['description']}.
        """ + ", ".join(f'<a href="{u}">{n}</a>' for n, u in talk['links']) + "</li>"
        for talk in DATA.get('talks', [])
    ])

    # Generate HTML list for publications
    bib_data = parse_file(
        pkg_resources.files(__package__).joinpath('data/references.bib'),
    )
    style = find_plugin('pybtex.style.formatting', 'plain')()
    formatted_bib = style.format_bibliography(bib_data)
    publications_html = "\n".join([
        "<li>{entry}</li>".format(entry = entry.text.render_as('html'))
        for entry in formatted_bib
    ])

    # Combine all content
    content = f"""
    <p>
        {INTRO}
    </p>
    <p class="mt-3">
        <strong>Stay in touch:</strong> subscribe to the <a href="{DATA.get('mailing_list', '')}">MadSuite mailing list</a> for updates.
    </p>
    <h2 class="mt-5">What's MadSuite?</h2>
    <p>
        {DESCRIPTION}
    </p>
    <h2 class="mt-5">News</h2>
    <ul>
        {news_html}
    </ul>
    <h2 class="mt-5">Useful Resources</h2>
    <ul>
        {resources_html}
    </ul>
    <h2 class="mt-5">Members</h2>
    <ul>
        {members_html}
    </ul>
    <h2 class="mt-5">Packages</h2>
    {packages_html}
    <h2 class="mt-5">Publications</h2>
    <ul>
        {publications_html}
    </ul>
    <h2 class="mt-5">Tutorials and Talks</h2>
    <ul>
        {talks_html}
    </ul>
    """

    # Generate the HTML file
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR)
    generate_html(os.path.join(BUILD_DIR, "index.html"), content, TEMPLATE, TITLE, YEAR, LINKS)

    # Create a CNAME file
    cname_path = os.path.join(BUILD_DIR, "CNAME")
    with open(cname_path, "w") as f:
        f.write(DOMAIN)

    # Move assets to the build directory
    assets_src = pkg_resources.files(__package__).joinpath('assets')
    assets_dest = os.path.join(BUILD_DIR, 'assets')
    shutil.copytree(assets_src, assets_dest)

def serve():
    # Do initial build before starting
    print("Running initial build...")
    build()

    server = Server()
    server.watch(
        pkg_resources.files(__package__),
        build,
    )
    server.serve(root=BUILD_DIR, port=8000) 

def deploy():
    print("Running initial build...")
    build()
    
    """Deploy the contents of _build to the gh-pages branch."""
    # Define the branch name
    branch_name = "gh-pages"

    # Ensure the _build directory exists
    if not os.path.exists(BUILD_DIR):
        raise Exception(f"The build directory {BUILD_DIR} does not exist. Run the build process first.")

    # Initialize a new Git repo inside the _build directory
    subprocess.run(['git', 'init'], cwd=BUILD_DIR, check=True)

    # Set up the remote repository (assumes origin is set up)
    # In GitHub Actions, push over HTTPS with the workflow token; locally, use SSH.
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY', 'madsuite-org/madsuite-org.github.io')
    remote = f'https://x-access-token:{token}@github.com/{repo}.git' if token else f'git@github.com:{repo}.git'
    subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=BUILD_DIR, check=True)

    # Checkout a new branch (or switch to it if it exists)
    subprocess.run(['git', 'checkout', '-B', branch_name], cwd=BUILD_DIR, check=True)

    # Add all the files to staging area
    subprocess.run(['git', 'add', '.'], cwd=BUILD_DIR, check=True)

    # Commit the changes
    subprocess.run(['git', 'commit', '-m', 'Deploy to GitHub Pages'], cwd=BUILD_DIR, check=True)
    # Force push to the gh-pages branch
    subprocess.run(['git', 'push', '--force', '--set-upstream', 'origin', branch_name], cwd=BUILD_DIR, check=True)

    print("Successfully deployed to GitHub Pages.")
