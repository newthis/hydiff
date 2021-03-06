"""
    Script to aggregate the results from an experiment.

    Input: source folder path, e.g.
    python3 evaluate_cost_hydiff.py blazer_login_unsafe/hydiff-out- 30 1800 30

"""
import sys
import csv
import statistics
import math
import numpy
import re

# do not change this parameters
START_INDEX = 1

if __name__ == '__main__':

    if len(sys.argv) != 5:
        raise Exception("usage: fuzzer-out-dir n timeout stepsize")

    fuzzerOutDir = sys.argv[1]
    NUMBER_OF_EXPERIMENTS = int(sys.argv[2])
    EXPERIMENT_TIMEOUT = int(sys.argv[3])
    STEP_SIZE = int(sys.argv[4])

    fileNamePatternSPF = re.compile(r"sync:spf,src:\d{6}")
    fileNamePatternID = re.compile(r"id:\d{6}")

    # Read data
    collected_data = []
    time_delta_greater_zero = {}
    delta_greater_zero_src = {}
    for i in range(START_INDEX, NUMBER_OF_EXPERIMENTS+1):
        experimentFolderPath = fuzzerOutDir + str(i)

        # Collect all time info from export info from SPF.
        spf_time_info = {}
        dataFile = experimentFolderPath + "/spf/export-statistic.txt"
        with open(dataFile,'r') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=',')
            next(csvreader) # skip first row
            for row in csvreader:
                fileName = fileNamePatternID.findall(row[2])[0]
                spf_time_info[fileName] = int(row[0])

        # Get time first delta > 0 in SPF.
        time_delta_greater_zero_spf = EXPERIMENT_TIMEOUT
        dataFile = experimentFolderPath + "/spf-replay/path_costs.csv"
        with open(dataFile,'r') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=';')
            next(csvreader) # skip first row
            for row in csvreader:
                if row[0].startswith("synced file"): continue
                fileName = row[1]
                if "sync:spf" in fileName:
                    fileNameInSPFExportFile = fileNamePatternSPF.findall(row[1])[0].replace("sync:spf,src", "id")
                    if "highscore" in fileName:
                        time_delta_greater_zero_spf = spf_time_info[fileNameInSPFExportFile]
                        break

        # Get time first delta > 0 in AFL.
        time_delta_greater_zero_afl = EXPERIMENT_TIMEOUT
        dataFile = experimentFolderPath + "/afl/path_costs.csv"
        with open(dataFile,'r') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=';')
            next(csvreader) # skip first row
            for row in csvreader:
                currentTime = int(row[0])
                fileName = row[1]
                if "highscore" in fileName:
                    time_delta_greater_zero_afl = currentTime
                    break

        # Get best time from AFL and SPF
        if time_delta_greater_zero_afl < time_delta_greater_zero_spf:
            time_delta_greater_zero[i] = time_delta_greater_zero_afl
            delta_greater_zero_src[i] = 'afl'
        elif time_delta_greater_zero_afl > time_delta_greater_zero_spf:
            time_delta_greater_zero[i] = time_delta_greater_zero_spf
            delta_greater_zero_src[i] = 'spf'
        else:
            time_delta_greater_zero[i] = time_delta_greater_zero_afl
            delta_greater_zero_src[i] = 'alf=spf'

        # Collect highscores for AFL.
        data_afl = {}
        dataFile = experimentFolderPath + "/afl/path_costs.csv"
        with open(dataFile,'r') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=';')
            timeBucket = STEP_SIZE
            next(csvreader) # skip first row
            currentHighscore = 0
            for row in csvreader:
                currentTime = int(row[0])
                fileName = row[1]
                containsHighscore = "highscore" in fileName
                currentScore = int(row[5])
                while currentTime > timeBucket:
                    data_afl[timeBucket] = currentHighscore
                    timeBucket += STEP_SIZE
                if containsHighscore:
                    currentHighscore = currentScore
                if timeBucket > EXPERIMENT_TIMEOUT:
                    break
            # fill data with last known value if not enough information
            while timeBucket <= EXPERIMENT_TIMEOUT:
                data_afl[timeBucket] = currentHighscore
                timeBucket += STEP_SIZE

        # Collect highscores for SPF.
        data_spf = {}
        dataFile = experimentFolderPath + "/spf-replay/path_costs.csv"
        with open(dataFile,'r') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=';')
            timeBucket = STEP_SIZE
            next(csvreader) # skip first row
            currentHighscore = 0
            for row in csvreader:
                if row[0].startswith("synced file"): continue
                fileName = row[1]
                if not "sync:spf" in fileName: continue
                id = fileNamePatternSPF.findall(fileName)[0].replace("sync:spf,src", "id")
                currentTime = spf_time_info[id]
                containsHighscore = "highscore" in fileName
                currentScore = int(row[5])
                while (currentTime > timeBucket):
                    data_spf[timeBucket] = currentHighscore
                    timeBucket += STEP_SIZE
                if containsHighscore:
                    currentHighscore = currentScore
                if timeBucket > EXPERIMENT_TIMEOUT:
                    break
            # fill data with last known value if not enough information
            while timeBucket <= EXPERIMENT_TIMEOUT:
                data_spf[timeBucket] = currentHighscore
                timeBucket += STEP_SIZE

        # Merge highscores from AFL and SPF.
        timeBucket = STEP_SIZE
        data = {}
        while timeBucket <= EXPERIMENT_TIMEOUT:
            data[timeBucket] = max(data_afl[timeBucket], data_spf[timeBucket])
            timeBucket += STEP_SIZE
        collected_data.append(data)

    # Aggregate dataFile
    mean_values = {}
    error_values = {}
    max_values = {}

    delta_values = {}
    for i in range(STEP_SIZE, EXPERIMENT_TIMEOUT+1, STEP_SIZE):
        delta_values[i] = []
        for j in range(START_INDEX-1, NUMBER_OF_EXPERIMENTS):
            delta_values[i].append(collected_data[j][i])
        mean_values[i] = "{0:.2f}".format(sum(delta_values[i])/float(NUMBER_OF_EXPERIMENTS))
        error_values[i] = "{0:.2f}".format(1.960 * numpy.std(delta_values[i])/float(math.sqrt(NUMBER_OF_EXPERIMENTS)))
        max_values[i] = max(delta_values[i])

    # Write collected data
    headers = ['seconds', 'avg_highscore', 'ci', 'maximum']
    outputFileName = fuzzerOutDir + "results-n=" + str(NUMBER_OF_EXPERIMENTS) + "-t=" + str(EXPERIMENT_TIMEOUT) + "-s=" + str(STEP_SIZE) + ".csv"
    print (outputFileName)
    with open(outputFileName, "w") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for timeBucket in range(STEP_SIZE, EXPERIMENT_TIMEOUT+1, STEP_SIZE):
            values = {'seconds' : int(timeBucket)}
            values['avg_highscore'] = mean_values[timeBucket]
            values['ci'] = error_values[timeBucket]
            values['maximum'] = max_values[timeBucket]
            writer.writerow(values)

        time_values = list(time_delta_greater_zero.values())
        deltaGreaterZero_sources = list(delta_greater_zero_src.values())
        if len(time_values) == NUMBER_OF_EXPERIMENTS:
            avg_time = "{0:.2f}".format(sum(time_values)/float(NUMBER_OF_EXPERIMENTS))
            error = "{0:.2f}".format(1.960 * numpy.std(time_values)/float(math.sqrt(NUMBER_OF_EXPERIMENTS)))
            csv_file.write("\ntime delta>0:\n" + str(avg_time) + " (+/- " + str(error) + ")\ndelta>0Times=" + str(time_values) + "\ndelta>0_src=" + str(deltaGreaterZero_sources) + "\ndeltas=" + str(delta_values[EXPERIMENT_TIMEOUT]) + "\ndeltas(30s)=" + str(delta_values[30]))
        else:
            csv_file.write("\ntime delta>0: -\ndelta>0Times=" + str(time_values) + "\ndelta>0_src=" + str(deltaGreaterZero_sources) + "\ndeltas=" + str(delta_values[EXPERIMENT_TIMEOUT]) + "\ndeltas(30s)=" + str(delta_values[30]))
