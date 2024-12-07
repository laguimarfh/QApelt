from django.shortcuts import render, redirect
from .forms import FileUploadForm
import pandas as pd
import logging
from datetime import datetime
from .models import CarData

logger = logging.getLogger(__name__)

def extract_point(panel_string):
    """Extract the point number from the panel string."""
    return panel_string.split(' ')[1] if ' ' in panel_string else panel_string

def calculate_latest(df, colour_code):
    """Calculate the latest car sequence for the same colour code."""
    latest_cars = df[df['Colour Code'] == colour_code].shape[0]
    if latest_cars == 0:
        return "1 car ago"
    else:
        return f"{latest_cars + 1} cars ago"

def get_url_for_colour(colour_code):
    """Get the URL for the given colour code."""
    urls = {
        '8X5': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/8X5.png?csf=1&web=1&e=m3Egzi',
        '085': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/85.png?csf=1&web=1&e=ANCzp4',
        '4Y5': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/4Y5.png?csf=1&web=1&e=D9VUKT',
        '6X4': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/6X4.png?csf=1&web=1&e=fORxuy',
        '223': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/223.png?csf=1&web=1&e=ViEknw',
        '3R1': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/3R1.png?csf=1&web=1&e=rW3o0j',
        '1L2': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/1L2.png?csf=1&web=1&e=BtQDQn',
        '8Y6': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/1L8.png?csf=1&web=1&e=TKqqFZ',
        '1L8': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/1L2.png?csf=1&web=1&e=BtQDQn',
        '1L1': 'https://myteams.toyota.com/:i:/r/sites/sTRiskManagement/Shared%20Documents/General/Kaizen/Car%20Colours/1L1.png?csf=1&web=1&e=BLShcb',
    }
    return urls.get(colour_code, '')

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Handle file upload separately
                if 'file' not in request.FILES:
                    logger.error('File not uploaded.')
                    return render(request, 'fileloader/upload.html', {'form': form, 'error': 'File not uploaded.'})

                file = request.FILES['file'].read().decode('utf-8')
                lines = file.splitlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Retrieve form data
                body_no = form.cleaned_data['body_no']
                date = form.cleaned_data['date']

                # Define the initial columns for the DataFrame
                columns = ['Latest', 'Primer', 'URL', 'Date', 'Body No.', 'Colour Code']
                data_row = {}
                point_counter = 1

                # Skip the header and empty lines
                for line in lines[1:]:  # Skip the first line (header)
                    if not line.strip():
                        continue

                    data = line.strip().split(',')
                    if len(data) < 42:  # Ensure there's enough data to extract
                        logger.warning('Line skipped, not enough data: %s', line)
                        continue

                    # Define new columns dynamically based on the point number
                    if point_counter == 1:
                        data_row['Body No.'] = body_no
                        data_row['Date'] = date
                        data_row['Colour Code'] = data[27].strip('" ')
                        data_row['Primer'] = data[35].strip('"')
                        data_row['URL'] = get_url_for_colour(data_row['Colour Code'])

                    point_number = extract_point(data[5])
                    data_row[f'{point_counter}C'] = data[25].strip()
                    data_row[f'{point_counter}B'] = data[33].strip()
                    data_row[f'{point_counter}P'] = data[41].strip()
                    point_counter += 1

                columns += [f'{i}C' for i in range(1, point_counter)]
                columns += [f'{i}B' for i in range(1, point_counter)]
                columns += [f'{i}P' for i in range(1, point_counter)]

                # Calculate the "Latest" column
                excel_path = 'uploads/output.xlsx'
                try:
                    df_existing = pd.read_excel(excel_path)
                    logger.debug('Existing Excel file found and read.')
                except FileNotFoundError:
                    df_existing = pd.DataFrame(columns=columns)
                    logger.debug('Excel file not found. A new one will be created.')

                latest_value = calculate_latest(df_existing, data_row['Colour Code'])
                data_row['Latest'] = latest_value

                # Create DataFrame with the new row, ensuring "Latest", "Primer", "URL", and "Date" are first
                df_row = pd.DataFrame([data_row], columns=['Latest', 'Primer', 'URL', 'Date'] + [col for col in columns if col not in ['Latest', 'Primer', 'URL', 'Date']])
                logger.debug('DataFrame created from parsed data: %s', df_row)

                # Append the new data
                df_combined = pd.concat([df_existing, df_row], ignore_index=True)
                logger.debug('Data combined with existing DataFrame: %s', df_combined)

                # Save to Excel
                df_combined.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                # Save to database
                car_data = CarData(
                    latest=data_row['Latest'],
                    primer=data_row['Primer'],
                    url=data_row['URL'],
                    date=date,  # Directly assigning the date from the form
                    body_no=data_row['Body No.'],
                    colour_code=data_row['Colour Code']
                )

                for i in range(1, point_counter):
                    setattr(car_data, f'{i}C', data_row.get(f'{i}C'))
                    setattr(car_data, f'{i}B', data_row.get(f'{i}B'))
                    setattr(car_data, f'{i}P', data_row.get(f'{i}P'))

                car_data.save()

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
                return render(request, 'peltloader/upload.html', {'form': form, 'error': 'Error processing file.'})
        else:
            logger.debug('Form is not valid.')
            return render(request, 'peltloader/upload.html', {'form': form})
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})



"""
import logging

logger = logging.getLogger(__name__)

def extract_point(panel_string):
    #Extract the point number from the panel string.
    return panel_string.split(' ')[1] if ' ' in panel_string else panel_string

def calculate_previous_car(df, colour_code):
    #Calculate the previous car sequence for the same colour code.
    previous_cars = df[df['Colour Code'] == colour_code].shape[0]
    if previous_cars == 0:
        return "1 car ago"
    else:
        return f"{previous_cars + 1} cars ago"

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save()
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Read and parse the .prn file
                with open(upload.file.path, 'r') as file:
                    lines = file.readlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Define the initial columns for the DataFrame
                columns = ['Measurement Date', 'Body Number', 'Upload Date', 'Operator', 'Colour Code', 'Primer Code']
                data_row = {}
                point_counter = 1

                # Skip the header and empty lines
                for line in lines[1:]:  # Skip the first line (header)
                    if not line.strip():
                        continue

                    data = line.strip().split(',')
                    if len(data) < 42:  # Ensure there's enough data to extract
                        logger.warning('Line skipped, not enough data: %s', line)
                        continue

                    # Define new columns dynamically based on the point number
                    if point_counter == 1:
                        data_row['Measurement Date'] = data[0].strip('"')
                        data_row['Body Number'] = upload.entry1
                        data_row['Upload Date'] = upload.entry2
                        data_row['Operator'] = data[3].strip('" ')
                        data_row['Colour Code'] = data[27].strip('" ')
                        data_row['Primer Code'] = data[35].strip('"')

                    point_number = extract_point(data[5])
                    data_row[f'{point_counter}C'] = data[25].strip()
                    data_row[f'{point_counter}B'] = data[33].strip()
                    data_row[f'{point_counter}P'] = data[41].strip()
                    point_counter += 1

                columns += [f'{i}C' for i in range(1, point_counter)]
                columns += [f'{i}B' for i in range(1, point_counter)]
                columns += [f'{i}P' for i in range(1, point_counter)]
                columns.append('Previous Car')

                df_row = pd.DataFrame([data_row], columns=columns)
                logger.debug('DataFrame created from parsed data: %s', df_row)

                # Create or update an Excel file
                excel_path = 'uploads/output.xlsx'
                try:
                    df_existing = pd.read_excel(excel_path)
                    logger.debug('Existing Excel file found and read.')
                except FileNotFoundError:
                    df_existing = pd.DataFrame(columns=columns)
                    logger.debug('Excel file not found. A new one will be created.')

                # Calculate the "Previous Car" column
                df_row['Previous Car'] = calculate_previous_car(df_existing, data_row['Colour Code'])

                # Append the new data
                df_combined = pd.concat([df_existing, df_row], ignore_index=True)
                logger.debug('Data combined with existing DataFrame: %s', df_combined)

                # Save to Excel
                df_combined.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
        else:
            logger.debug('Form is not valid.')
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})

"""
"""
import logging

logger = logging.getLogger(__name__)

def extract_point(panel_string):
    '''Extract the point number from the panel string.'''
    return panel_string.split(' ')[1] if ' ' in panel_string else panel_string

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save()
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Read and parse the .prn file
                with open(upload.file.path, 'r') as file:
                    lines = file.readlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Define the initial columns for the DataFrame
                columns = ['ID', 'Measurement Date', 'Body Number', 'Upload Date', 'Operator', 'Colour Code', 'Primer Code']
                data_row = {}
                point_counter = 1

                # Process each line to extract points data
                for line in lines:
                    data = line.strip().split(',')
                    if len(data) < 42:  # Ensure there's enough data to extract
                        logger.warning('Line skipped, not enough data: %s', line)
                        continue

                    # Define new columns dynamically based on the point number
                    if point_counter == 1:
                        data_row['Measurement Date'] = data[0].strip('"')
                        data_row['Body Number'] = upload.entry1
                        data_row['Upload Date'] = upload.entry2
                        data_row['Operator'] = data[3].strip('" ')
                        data_row['Colour Code'] = data[27].strip('" ')
                        data_row['Primer Code'] = data[35].strip('"')

                    point_number = extract_point(data[5])
                    data_row[f'{point_counter}C'] = data[25].strip()
                    data_row[f'{point_counter}B'] = data[33].strip()
                    data_row[f'{point_counter}P'] = data[41].strip()
                    point_counter += 1

                columns += [f'{i}C' for i in range(1, point_counter)]
                columns += [f'{i}B' for i in range(1, point_counter)]
                columns += [f'{i}P' for i in range(1, point_counter)]

                # Create DataFrame with the new row
                df_row = pd.DataFrame([data_row], columns=columns)
                logger.debug('DataFrame created from parsed data: %s', df_row)

                # Create or update an Excel file
                excel_path = 'uploads/output.xlsx'
                try:
                    df_existing = pd.read_excel(excel_path)
                    logger.debug('Existing Excel file found and read.')
                    next_id = df_existing['ID'].max() + 1  # Get next ID
                except FileNotFoundError:
                    df_existing = pd.DataFrame(columns=columns)
                    next_id = 1  # Start ID from 1
                    logger.debug('Excel file not found. A new one will be created.')

                # Set the new ID
                df_row['ID'] = next_id

                # Append the new data
                df_combined = pd.concat([df_existing, df_row], ignore_index=True)
                logger.debug('Data combined with existing DataFrame: %s', df_combined)

                # Save to Excel
                df_combined.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
        else:
            logger.debug('Form is not valid.')
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})


"""

"""
import logging

logger = logging.getLogger(__name__)

def extract_point(panel_string):
    '''Extract the point number from the panel string.'''
    return panel_string.split(' ')[1] if ' ' in panel_string else panel_string

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save()
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Read and parse the .prn file
                with open(upload.file.path, 'r') as file:
                    lines = file.readlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Define the initial columns for the DataFrame
                columns = ['Measurement Date', 'Body Number', 'Upload Date', 'Operator', 'Colour Code', 'Primer Code']
                data_row = {}
                point_counter = 1

                # Process each line to extract points data
                for line in lines:
                    data = line.strip().split(',')
                    if len(data) < 42:  # Ensure there's enough data to extract
                        logger.warning('Line skipped, not enough data: %s', line)
                        continue

                    # Define new columns dynamically based on the point number
                    if point_counter == 1:
                        data_row['Measurement Date'] = data[0].strip('"')
                        data_row['Body Number'] = upload.entry1
                        data_row['Upload Date'] = upload.entry2
                        data_row['Operator'] = data[3].strip('" ')
                        data_row['Colour Code'] = data[27].strip('" ')
                        data_row['Primer Code'] = data[35].strip('"')

                    point_number = extract_point(data[5])
                    data_row[f'{point_counter}C'] = data[25].strip()
                    data_row[f'{point_counter}B'] = data[33].strip()
                    data_row[f'{point_counter}P'] = data[41].strip()
                    point_counter += 1

                # Ensure columns are ordered correctly
                columns += [f'{i}C' for i in range(1, point_counter)]
                columns += [f'{i}B' for i in range(1, point_counter)]
                columns += [f'{i}P' for i in range(1, point_counter)]

                df_row = pd.DataFrame([data_row], columns=columns)
                logger.debug('DataFrame created from parsed data: %s', df_row)

                # Create or update an Excel file
                excel_path = 'uploads/output.xlsx'
                try:
                    df_existing = pd.read_excel(excel_path)
                    logger.debug('Existing Excel file found and read.')
                except FileNotFoundError:
                    df_existing = pd.DataFrame(columns=columns)
                    logger.debug('Excel file not found. A new one will be created.')

                # Append the new data
                df_combined = pd.concat([df_existing, df_row], ignore_index=True)
                logger.debug('Data combined with existing DataFrame: %s', df_combined)

                # Save to Excel
                df_combined.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
        else:
            logger.debug('Form is not valid.')
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})


"""
"""

import logging

logger = logging.getLogger(__name__)

def extract_point(panel_string):
    '''Extract the point number from the panel string.'''
    return panel_string.split(' ')[1] if ' ' in panel_string else panel_string

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save()
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Read and parse the .prn file
                with open(upload.file.path, 'r') as file:
                    lines = file.readlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Define the initial columns for the DataFrame
                columns = ['Measurement Date', 'Body Number', 'Upload Date', 'Operator', 'Colour Code', 'Primer Code']
                data_row = {}
                point_counter = 1

                # Process each line to extract points data
                for line in lines:
                    data = line.strip().split(',')
                    if len(data) < 42:  # Ensure there's enough data to extract
                        logger.warning('Line skipped, not enough data: %s', line)
                        continue

                    # Define new columns dynamically based on the point number
                    if point_counter == 1:
                        data_row['Measurement Date'] = data[0].strip('"')
                        data_row['Body Number'] = upload.entry1
                        data_row['Upload Date'] = upload.entry2
                        data_row['Operator'] = data[3].strip('" ')
                        data_row['Colour Code'] = data[27].strip('" ')
                        data_row['Primer Code'] = data[35].strip('"')

                    point_number = extract_point(data[5])
                    data_row[f'{point_counter}C'] = data[25].strip()
                    data_row[f'{point_counter}B'] = data[33].strip()
                    data_row[f'{point_counter}P'] = data[41].strip()
                    point_counter += 1

                columns += [f'{i}C' for i in range(1, point_counter)]
                columns += [f'{i}B' for i in range(1, point_counter)]
                columns += [f'{i}P' for i in range(1, point_counter)]

                df_row = pd.DataFrame([data_row], columns=columns)
                logger.debug('DataFrame created from parsed data: %s', df_row)

                # Create or update an Excel file
                excel_path = 'uploads/output.xlsx'
                try:
                    df_existing = pd.read_excel(excel_path)
                    logger.debug('Existing Excel file found and read.')
                except FileNotFoundError:
                    df_existing = pd.DataFrame(columns=columns)
                    logger.debug('Excel file not found. A new one will be created.')

                # Replace the data in the Excel file with the new data
                df_combined = df_row
                logger.debug('Data combined with existing DataFrame: %s', df_combined)

                # Save to Excel
                df_combined.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
        else:
            logger.debug('Form is not valid.')
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})


"""
"""

import logging

logger = logging.getLogger(__name__)

def extract_point(panel_string):
    #Extract the point number from the panel string
    return panel_string.split(' ')[1] if ' ' in panel_string else panel_string

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save()
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Read and parse the .prn file
                with open(upload.file.path, 'r') as file:
                    lines = file.readlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Define the columns for the DataFrame
                columns = ['Measurement Date', 'Body Number', 'Upload Date', 'operator', 'Colour Code', 'Primer Code', 'Point number', 'Clear', 'Base', 'Primer']
                data_rows = []

                # Process each line
                for line in lines:
                    data = line.strip().split(',')
                    if len(data) < 42:  # Ensure there's enough data to extract
                        logger.warning('Line skipped, not enough data: %s', line)
                        continue
                    row = [
                        data[0].strip('"'),                     # D'Measurement Date
                        upload.entry1,               # Body Number
                        upload.entry2,               # Upload Date
                        data[3].strip('" '),        # Operator
                        data[27].strip('" '),                                          # Colour Code
                        data[35].strip('"'),                     # Primer Code
                        extract_point(data[5]),      # Point number
                        data[25],               # Clear
                        data[33],               # Base
                        data[41],               # Primer
                    ]
                    data_rows.append(row)
                
                logger.debug('Processed data rows: %s', data_rows)

                df_rows = pd.DataFrame(data_rows, columns=columns)
                logger.debug('DataFrame created from parsed data: %s', df_rows)

                # Create or update an Excel file
                excel_path = 'uploads/output8.xlsx'
                try:
                    df_existing = pd.read_excel(excel_path)
                    logger.debug('Existing Excel file found and read.')
                except FileNotFoundError:
                    df_existing = pd.DataFrame(columns=columns)
                    logger.debug('Excel file not found. A new one will be created.')

                # Append the new data
                df_combined = pd.concat([df_existing, df_rows], ignore_index=True)
                logger.debug('Data combined with existing DataFrame: %s', df_combined)

                # Save to Excel
                df_combined.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
        else:
            logger.debug('Form is not valid.')
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})
"""

"""
import logging

logger = logging.getLogger(__name__)

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save()
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Read and parse the .prn file
                with open(upload.file.path, 'r') as file:
                    lines = file.readlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Process the lines and split by comma
                if lines:
                    headers = lines[0].strip().split(',')
                    data_rows = [line.strip().split(',') for line in lines[1:]]
                    logger.debug('Parsed headers: %s', headers)
                    logger.debug('Parsed data rows: %s', data_rows)

                    df_rows = pd.DataFrame(data_rows, columns=headers)
                    logger.debug('DataFrame created from parsed data: %s', df_rows)
                else:
                    logger.error('File is empty.')
                    return render(request, 'fileloader/upload.html', {'form': form, 'error': 'File is empty.'})

                # Create or update an Excel file
                excel_path = 'uploads/output7.xlsx'
                try:
                    df_existing = pd.read_excel(excel_path)
                    logger.debug('Existing Excel file found and read.')
                except FileNotFoundError:
                    df_existing = pd.DataFrame(columns=headers)
                    logger.debug('Excel file not found. A new one will be created.')

                # Append the new data
                df_combined = pd.concat([df_existing, df_rows], ignore_index=True)
                logger.debug('Data combined with existing DataFrame: %s', df_combined)

                # Save to Excel
                df_combined.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
        else:
            logger.debug('Form is not valid.')
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})

"""

"""
import logging

logger = logging.getLogger(__name__)

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():  # Correcting the typo here
            upload = form.save()
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Read and parse the .prn file
                with open(upload.file.path, 'r') as file:
                    lines = file.readlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Process the lines and split by comma
                data_rows = [line.strip().split(',') for line in lines]
                logger.debug('Parsed data rows: %s', data_rows)

                # Ensure headers and data columns match
                num_columns = max(len(row) for row in data_rows)
                if len(data_rows) > 1:
                    headers = data_rows[0] if len(data_rows[0]) == num_columns else [f'Column_{i+1}' for i in range(num_columns)]
                    data = data_rows[1:]
                else:
                    headers = [f'Column_{i+1}' for i in range(num_columns)]
                    data = data_rows
                
                df_rows = pd.DataFrame(data, columns=headers)
                logger.debug('DataFrame created from parsed data: %s', df_rows)

                # Create or update an Excel file
                excel_path = 'uploads/output6.xlsx'
                try:
                    df_existing = pd.read_excel(excel_path)
                    logger.debug('Existing Excel file found and read.')
                except FileNotFoundError:
                    df_existing = pd.DataFrame()
                    logger.debug('Excel file not found. A new one will be created.')

                # Append the new data
                df_combined = pd.concat([df_existing, df_rows], ignore_index=True)
                logger.debug('Data combined with existing DataFrame: %s', df_combined)

                # Save to Excel
                df_combined.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
        else:
            logger.debug('Form is not valid.')
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})

"""
"""
import logging

logger = logging.getLogger(__name__)

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save()
            logger.debug('Form is valid. File uploaded successfully.')
            try:
                # Read and parse the .prn file
                with open(upload.file.path, 'r') as file:
                    lines = file.readlines()
                logger.debug('File read successfully. Content: %s', lines)

                # Combine all lines to form the ASCII content
                ascii_content = ''.join(lines).replace('\n', ' ')
                logger.debug('Combined ASCII content: %s', ascii_content)

                # Create or update an Excel file
                excel_path = 'uploads/output4.xlsx'
                try:
                    df = pd.read_excel(excel_path)
                    logger.debug('Excel file found and read.')
                except FileNotFoundError:
                    df = pd.DataFrame(columns=['ASCII_Content', 'Entry1', 'Entry2'])
                    logger.debug('Excel file not found. Creating new one.')

                # Append the new data
                new_row = pd.DataFrame([{'ASCII_Content': ascii_content, 'Entry1': upload.entry1, 'Entry2': upload.entry2}])
                df = pd.concat([df, new_row], ignore_index=True)
                logger.debug('Data appended to DataFrame: %s', new_row)

                df.to_excel(excel_path, index=False)
                logger.debug('DataFrame saved to Excel file.')

                return redirect('success')
            except Exception as e:
                logger.error('Error processing file: %s', e)
        else:
            logger.debug('Form is not valid.')
    else:
        form = FileUploadForm()
    return render(request, 'peltloader/upload.html', {'form': form})
"""