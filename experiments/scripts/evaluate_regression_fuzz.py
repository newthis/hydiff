"""
    Script to aggregate the results from an experiment.

    Input: source folder path, e.g.
    python3 evaluate_regression_fuzz.py tcas_v1/fuzzer-out- 30 600 30

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

    fileNamePatternAFL = re.compile(r"sync:spf,src:\d{6}")
    fileNamePatternSPF = re.compile(r"id:\d{6}")

    # Read data
    collected_outDiff_data = []
    collected_decDiff_data = []
    time_first_odiff = {}
    for i in range(START_INDEX, NUMBER_OF_EXPERIMENTS+1):
        experimentFolderPath = fuzzerOutDir + str(i)

        odiff_collector = {}
        ddiff_collector = {}

        dataFile = experimentFolderPath + "/afl/path_costs.csv"
        with open(dataFile,'r') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=';')
            timeBucket = STEP_SIZE
            next(csvreader) # skip first row
            previousOutDiffValue = 0
            previousDecDiffValue = 0
            currentOutDiffValue = 0
            currentDecDiffValue = 0
            for row in csvreader:
                currentTime = int(row[0])
                fileName = row[1]
                containsOutDiff = "+odiff" in fileName or "+crash" in fileName
                containsDecDiff = "+ddiff" in fileName

                if i not in time_first_odiff and containsOutDiff:
                    time_first_odiff[i] = currentTime

                if containsOutDiff:
                    currentOutDiffValue = previousOutDiffValue + 1

                if containsDecDiff:
                    currentDecDiffValue = previousDecDiffValue + 1

                while (currentTime > timeBucket):
                    odiff_collector[timeBucket] = previousOutDiffValue
                    ddiff_collector[timeBucket] = previousDecDiffValue
                    timeBucket += STEP_SIZE

                previousOutDiffValue = currentOutDiffValue
                previousDecDiffValue = currentDecDiffValue

                if timeBucket > EXPERIMENT_TIMEOUT:
                    break

            # fill data with last known value if not enough information
            while timeBucket <= EXPERIMENT_TIMEOUT:
                odiff_collector[timeBucket] = previousOutDiffValue
                ddiff_collector[timeBucket] = previousDecDiffValue
                timeBucket += STEP_SIZE

        collected_outDiff_data.append(odiff_collector)
        collected_decDiff_data.append(ddiff_collector)

        if i not in time_first_odiff:
            time_first_odiff[i] = EXPERIMENT_TIMEOUT

    # Aggregate dataFile
    mean_values_outDiff = {}
    error_values_outDiff = {}
    mean_values_decDiff = {}
    error_values_decDiff = {}

    for i in range(STEP_SIZE, EXPERIMENT_TIMEOUT+1, STEP_SIZE):
        outDiff_values = []
        for j in range(START_INDEX-1, NUMBER_OF_EXPERIMENTS):
            outDiff_values.append(collected_outDiff_data[j][i])
        mean_values_outDiff[i] = "{0:.2f}".format(sum(outDiff_values)/float(NUMBER_OF_EXPERIMENTS))
        error_values_outDiff[i] = "{0:.2f}".format(1.960 * numpy.std(outDiff_values)/float(math.sqrt(NUMBER_OF_EXPERIMENTS)))

        decDiff_values = []
        for j in range(START_INDEX-1, NUMBER_OF_EXPERIMENTS):
            decDiff_values.append(collected_decDiff_data[j][i])
        mean_values_decDiff[i] = "{0:.2f}".format(sum(decDiff_values)/float(NUMBER_OF_EXPERIMENTS))
        error_values_decDiff[i] = "{0:.2f}".format(1.960 * numpy.std(decDiff_values)/float(math.sqrt(NUMBER_OF_EXPERIMENTS)))

    # Write collected data
    headers = ['seconds', 'avg_odiff', 'ci_odiff', 'avg_ddiff', 'ci_ddiff']
    outputFileName = fuzzerOutDir + "results-n=" + str(NUMBER_OF_EXPERIMENTS) + "-t=" + str(EXPERIMENT_TIMEOUT) + "-s=" + str(STEP_SIZE) + ".csv"
    print (outputFileName)
    with open(outputFileName, "w") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for timeBucket in range(STEP_SIZE, EXPERIMENT_TIMEOUT+1, STEP_SIZE):
            values = {'seconds' : int(timeBucket)}
            values['avg_odiff'] = mean_values_outDiff[timeBucket]
            values['ci_odiff'] = error_values_outDiff[timeBucket]
            values['avg_ddiff'] = mean_values_decDiff[timeBucket]
            values['ci_ddiff'] = error_values_decDiff[timeBucket]
            writer.writerow(values)

        time_values = list(time_first_odiff.values())
        min = min(time_values)
        if len(time_values) == NUMBER_OF_EXPERIMENTS:
            avg_time = "{0:.2f}".format(sum(time_values)/float(NUMBER_OF_EXPERIMENTS))
            error = "{0:.2f}".format(1.960 * numpy.std(time_values)/float(math.sqrt(NUMBER_OF_EXPERIMENTS)))
            csv_file.write("\ntime +odiff>0:\n" + str(avg_time) + " (+/- " + str(error) + ") min=" + str(min) + "\n+odiff_times=" + str(time_values) + "\n#odiffs=" + str(outDiff_values) + "\n#ddiffs=" + str(decDiff_values))
        else:
            csv_file.write("\ntime +odiff>0: -\n" + "min=" + str(min) + "\n+odiff_times=" + str(time_values) + "\n#odiffs=" + str(outDiff_values) + "\n#ddiffs=" + str(decDiff_values))
