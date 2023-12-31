import bibtexparser
import fitz

from csv import reader, writer
from datetime import datetime
from glob import glob
from os.path import dirname, exists, sep
from os import makedirs, system
from re import I, search, sub
from time import sleep

from utils.utils import normalize_to_ascii
from utils.utils import red, green, blue, yellow, underline


class PDFextractor:

    def __init__(self, ceph_mount_point, proceedings_directory, bibliography_directory, output_directory, log_directory = "extraction_logs"):
        self.ceph_mount_point = ceph_mount_point
        self.proceedings_directory = proceedings_directory
        self.bibliography_directory = bibliography_directory
        self.output_directory = output_directory
        self.log_directory = ceph_mount_point + log_directory
        if not exists(self.log_directory): makedirs(self.log_directory)

        now = datetime.now()
        self.start = ((str(now.year)) + "-" + (str(now.month).rjust(2,"0")) + "-" + (str(now.day).rjust(2,"0")) + "_" +
                      (str(now.hour).rjust(2,"0")) + "-" + (str(now.minute).rjust(2,"0")))
        
        self.log_file = self.log_directory + sep + self.start + "_log.csv"
        self.new_found_file = self.log_directory + sep + self.start + "_new_found.csv"
        self.not_found_file = self.log_directory + sep + self.start + "_not_found.csv"

    def bibliography(self, entry):
        """
        Extract unicode-formatted bibliography information from the entry.

        Args:
            entry: A dictionary serialised from the bibtex entry.
        Returns:
            A tuple containing bibkey, title, title as filename, the last names of the authors, the DOI and the page
            count of the publication; None if not applicable.
        """
        entry_in_unicode = bibtexparser.customization.convert_to_unicode(entry)
        bibkey, title, authors, doi, pages = (entry_in_unicode["ID"], 
                                              entry_in_unicode["title"], 
                                              entry_in_unicode.get("author", []),
                                              entry_in_unicode.get("doi", None), 
                                              entry_in_unicode.get("pages"))
        title_as_filename = self.convert_title_to_filename(title)
        last_names_of_authors = authors.split(" and ") if authors else []
        page_count = self.get_page_count(pages)
        if doi: doi.replace("\\", "")
        if page_count != None:
            return (bibkey, title, title_as_filename, authors, last_names_of_authors, doi, page_count)
        else:
            return None
        
    def check_page(self, page_text, title, authors, doi):
        """
        Check page text for title, authors and DOI and highlight for user.

        Args:
            page_text: The string representing the PDF page.
            title: The title of the publication.
            authors: The list of authors of the publication.
            doi: The DOI of the application.
        Returns:
            A string formatted to highlight title, authors and DOI in the terminal.
        """
        system("clear")
        print(underline("TITLE") + ": " + blue(title))
        print(underline("AUTHORS") + ": " + green(", ".join([author for author in authors])))
        print(underline("DOI") + ": " + yellow(doi if doi else "-"))
        print()
        edited_page_text = page_text.replace("ﬁ","fi")
        try:
            match = search(title.replace(" ", "[ \n]*"), edited_page_text, flags=I)
            if match:
                edited_page_text = sub(match.group(), blue(match.group()), edited_page_text, flags=I)
        except:
            edited_page_text = page_text.replace("ﬁ","fi")
        if doi:
            edited_page_text = edited_page_text.replace(doi, yellow(doi))
        for author in authors:
            edited_page_text = sub(author.split(" ")[0] + ".*?" + author.split(" ")[-1], green(author), edited_page_text, flags=I)
            match = search(author.split(" ")[0][0] + "[\. ]*" + author.split(" ")[-1], edited_page_text, flags=I)
            if match:
                edited_page_text = sub(match.group(), green(match.group()), edited_page_text, flags=I)
            edited_page_text = sub(author.split(" ")[-1], green(author.split(" ")[-1]), edited_page_text, flags=I)
        match = search("introduction", edited_page_text, flags=I)
        if match:
            edited_page_text = sub(match.group(), red(match.group()), edited_page_text, flags=I)
        match = search("abstract", edited_page_text, flags=I)
        if match:
            edited_page_text = sub(match.group(), red(match.group()), edited_page_text, flags=I)
        print(edited_page_text.strip())
        print()
        check = None
        while check not in ["y", "n", "i"]:
            check = input("Enter 'y' if correct; enter 'n' if wrong paper; enter 'i' if table of content, reference page, etc to skip page. ")
        return check

    def extract(self, venue, year, test):
        """
        Loads the proceedings PDFs and the bibfile for a specifica venue and year
        and extracts PDFs from proceeding for specified venue and year if found by
        DOI or title. Queries user to confirm or reject suggestions.

        'y' - displayed page is the first page of the paper in question.
        'n' - displayed page is the first page of another paper
        'i' - displayed page is skipped as it is not a first page of a paper (e.g. reference section page)

        Args:
            venue: The venue of the conference.
            year: The year of the conference.
            test: If True, suffixes output directory with '-test'.
        Returns:
            Tuple of number of papers found by doi and number of papers found by title.
        """
        print(venue, year)
        sleep(1)
        proceedings_pdf_filepaths = sorted(glob(self.ceph_mount_point + self.proceedings_directory + sep + 
                                                venue + sep + year + sep + 
                                                venue + "-" + year + "-" + "proceedings" + "*.pdf"))
        bibfile_path = (self.ceph_mount_point + self.bibliography_directory + sep +
                        venue + sep + year + sep + 
                        "conf" + "-" + venue + "-" + year + ".bib")
            
        if not exists(bibfile_path):
            return 0,0
        
        with open(bibfile_path) as bibfile:
            entries = [item for item in 
                       [self.bibliography(entry) for entry in bibtexparser.load(bibfile).entries] if item]

        entries_found_by_doi = {}
        entries_found_by_title = {}

        for proceeding_pdf_filepath in proceedings_pdf_filepaths:
            # get cached extraction data (by doi)
            by_doi_filepath = proceeding_pdf_filepath.replace(".pdf", "_found_by_doi.csv")
            if exists(by_doi_filepath):
                with open(by_doi_filepath) as by_doi_file:
                    csv_reader = reader(by_doi_file, delimiter=",")
                    for bibkey, title, title_as_filename, authors, doi, proceeding_pdf_filepath_without_ceph_mountpoint, from_page, to_page in csv_reader:
                        entries_found_by_doi[bibkey] = [doi, self.ceph_mount_point + proceeding_pdf_filepath_without_ceph_mountpoint, int(from_page), int(to_page)]
            # get cached extraction data (by title)
            by_title_filepath = proceeding_pdf_filepath.replace(".pdf", "_found_by_title.csv")
            if exists(by_title_filepath):
                with open(by_title_filepath) as by_title_file:
                    csv_reader = reader(by_title_file, delimiter=",")
                    for bibkey, title, title_as_filename, authors, doi, proceeding_pdf_filepath_without_ceph_mountpoint, from_page, to_page in csv_reader:
                        entries_found_by_title[bibkey] = [title_as_filename, self.ceph_mount_point + proceeding_pdf_filepath_without_ceph_mountpoint, int(from_page), int(to_page)]
            # read proceedings pdf and start extraction
            with fitz.open(proceeding_pdf_filepath) as pdf:
                for page_number, page in enumerate(pdf.pages()):
                    # get text of page
                    page_text = page.get_text()
                    # replace linebreaks with spaces
                    page_text_no_linebreaks = page_text.replace("\n", " ")
                    # reduce multiple spaces to single spaces and replace fi ligature
                    page_text_preprocessed = sub(" +", " ", page_text_no_linebreaks.lower()).replace("ﬁ","fi")

                    for bibkey, title, title_as_filename, authors, last_names_of_authors, doi, page_count in entries:
                        if bibkey not in entries_found_by_doi and bibkey not in entries_found_by_title:
                            if (doi and doi in page_text_no_linebreaks):
                                check = self.check_page(page_text, title, last_names_of_authors, doi)
                                if check == "y":
                                    entries_found_by_doi[bibkey] = [doi,
                                                                    proceeding_pdf_filepath, 
                                                                    page_number, page_number+page_count]
                                    with open(by_doi_filepath, "a") as by_doi_file:
                                        csv_writer = writer(by_doi_file, delimiter=",")
                                        csv_writer.writerow([bibkey, title, title_as_filename, authors, doi, proceeding_pdf_filepath.replace(self.ceph_mount_point, ""), page_number, page_number+page_count])
                                elif check == "i":
                                    break
                            elif (title.lower() in page_text_preprocessed):
                                check = self.check_page(page_text, title, last_names_of_authors, doi)
                                if check == "y":
                                    entries_found_by_title[bibkey] = [title_as_filename,
                                                                      proceeding_pdf_filepath, 
                                                                      page_number, page_number+page_count]
                                    with open(by_title_filepath, "a") as by_title_file:
                                        csv_writer = writer(by_title_file, delimiter=",")
                                        csv_writer.writerow([bibkey, title, title_as_filename, authors, doi, proceeding_pdf_filepath.replace(self.ceph_mount_point, ""), page_number, page_number+page_count])
                                elif check == "i":
                                    break
        
        # log bibkeys found neither by doi nor title
        for bibkey, title, title_as_filename, authors, last_names_of_authors, doi, page_count in entries:
            if bibkey not in entries_found_by_doi and bibkey not in entries_found_by_title:
                with open(self.not_found_file, "a") as not_found_file:
                    csv_writer = writer(not_found_file, delimiter=",")
                    csv_writer.writerow([bibkey, title, authors, doi])
        
        # create pdfs for bibkeys found by doi or title
        for entries_found, output_directory in [[entries_found_by_doi,
                                                 self.output_directory  + "-by-doi" + ("-test" if test else "")],
                                                [entries_found_by_title,
                                                 self.output_directory  + "-by-title" + ("-test" if test else "")]]:
            for bibkey, values in entries_found.items():
                doi_or_title_as_pathname, proceeding_pdf_filepath, from_page, to_page = values
                with fitz.open(proceeding_pdf_filepath) as pdf:
                    paper = fitz.open()
                    paper.insert_pdf(pdf, from_page=from_page, to_page=to_page)
                    paper_filepath = (output_directory + sep +
                                      venue + sep + year + sep +
                                      doi_or_title_as_pathname + ".pdf")
                    if not exists(dirname(paper_filepath)):
                        makedirs(dirname(paper_filepath))
                    if not exists(paper_filepath):
                        paper.save(paper_filepath)
                        with open(self.new_found_file, "a") as new_found_file:
                            csv_writer = writer(new_found_file, delimiter=",")
                            csv_writer.writerow([bibkey])

        return len(entries_found_by_doi), len(entries_found_by_title)

    def run(self, venue, year, test):
        """
        Runner to start extraction for year and venue and write results to overview file.

        Args:
            venue: The venue of the conference.
            year: The year of the conference.
            test: If True, suffixes output directory with '-test'.
        """
        year = str(year)
        paper_count = [0, 0]
        found_by_doi, found_by_title = self.extract(venue, year, test)
        paper_count[0] += found_by_doi
        paper_count[1] += found_by_title
        with open(self.log_file, "a") as file:
            csv_writer = writer(file, delimiter=",")
            csv_writer.writerow([self.proceedings_directory, venue, year, found_by_doi, "by doi", found_by_title, "by title"])

    def get_page_count(self, pages):
        """
        Get number of pages of paper from bibtex 'pages' value.

        Args:
            pages: The string representing the value of the 'pages' keys of a bibtex entry.
        Returns:
            None if pages invalid, 0 if only one page, or difference between last and first page.
        """
        if not pages:
            return None
        pages_split = pages.split("--")
        try:
            if len(pages_split) == 1:
                return 0
            else:
                return int(pages_split[1]) - int(pages_split[0])
        except ValueError:
            return None

    def convert_title_to_filename(self, title):
        """
        Convert title to ASCII, remove all non-alpha characters (except spaces),
        replace spaces with underline and lower string.

        Args:
            entry: A title as string.
        Returns:
            ASCII-formatted, lowered, underline-formatted version of the input title.
        """
        return "".join([normalize_to_ascii(character) for character in title if character.isalpha() or character == " "]).replace(" ", "_").lower()


if __name__ == "__main__":

    ceph_mount_point = "/media/wolfgang/Ceph"

    input("PLEASE CHECK MOUNT POINT AND DIRECTORIES!")
    exit()
    
    proceedings_directory = "/data-in-production/ir-anthology/sources/proceedings-by-venue"
    bibliography_directory = "/data-in-production/ir-anthology/conf"
    output_directory = "/data-in-production/ir-anthology/sources/papers-by-venue-extracted"
    log_directory = "/data-in-production/ir-anthology/scripts/extraction_logs"

    proceedings = {}

    for venue_filepath in sorted(glob(ceph_mount_point + proceedings_directory + sep + "*")):
        venue = venue_filepath.split(sep)[-1]
        for year_filepath in sorted(glob(venue_filepath + sep + "*")):
            year = year_filepath.split(sep)[-1]
            if venue not in proceedings:
                proceedings[venue] = []
            proceedings[venue].append(year)

    pdf_extractor = PDFextractor(ceph_mount_point,
                                 proceedings_directory,
                                 bibliography_directory,
                                 output_directory,
                                 log_directory)

    for venue in proceedings:
        for year in proceedings[venue]:
            pdf_extractor.run(venue, year, test = False)

    
